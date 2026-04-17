import streamlit as st
import os
import pandas as pd
from datetime import datetime
from src.config import HOMEWORKS_DIR, LOG_FILE
from src.db import (
    get_student_feedback, get_student_escalations, get_support_messages,
    add_support_message, mark_student_read, add_escalation,
    save_chat_message, get_chat_history, clear_chat_history
)
from src.services.homework_service import extract_text_from_file, validate_homework_relevance
from src.logger import setup_logger
from src.agent import load_lms_data

logger = setup_logger(__name__)

def log_interaction(query, response, context_docs):
    topics = [doc.metadata.get("topic", "unknown") for doc in context_docs] if context_docs else []
    topic = topics[0] if topics else "general"
    
    new_data = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "response": response,
        "topic_inferred": topic
    }])
    new_data.to_csv(LOG_FILE, mode='a', header=False, index=False)

def render_student_chat_tab(active_student):
    st.header("🎓 Ваш персональный ИИ-Куратор")
    st.markdown("Задавайте вопросы по лекциям, домашним заданиям или правилам платформы.")
    
    # Load history from DB if not in session
    if f"chat_loaded_{active_student['username']}" not in st.session_state:
        db_history = get_chat_history(active_student['username'])
        if not db_history:
            # Initial message
            st.session_state.messages = [
                {"role": "assistant", "content": "Привет! 👋 Я ваш ИИ-куратор. Я здесь, чтобы помочь вам с материалами курса, расписанием и любыми организационными вопросами. Чем могу помочь сегодня?", "context": None}
            ]
            save_chat_message(active_student['username'], "assistant", st.session_state.messages[0]["content"])
        else:
            st.session_state.messages = db_history
        st.session_state[f"chat_loaded_{active_student['username']}"] = True
    
    for msg in st.session_state.messages:
        avatar = "🎓" if msg["role"] == "assistant" else "🧑‍💻"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("context"):
                with st.expander("📚 Источники (Контекст)"):
                    for doc in msg["context"]:
                        st.caption(f"**Модуль:** {doc.metadata.get('module', 'N/A')} | **Тема:** {doc.metadata.get('topic', 'N/A')}")
            
    if prompt := st.chat_input("Напишите ваш вопрос здесь..."):
        # Save user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_chat_message(active_student['username'], "user", prompt)
        
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="🎓"):
            with st.spinner("Анализирую базу знаний... 🤔"):
                try:
                    formatted_history = [(m["role"], m["content"]) for m in st.session_state.messages[:-1] if m["role"] != "system"]
                    profile_str = f"Имя: {active_student['name']}\nКурс: {active_student['course']}\nУровень: {active_student['level']}\nПрогресс: {active_student['progress']}%"
                    
                    response = st.session_state.chain.invoke({
                        "input": prompt,
                        "chat_history": formatted_history,
                        "student_profile": profile_str,
                        "lms_data": load_lms_data()
                    })
                    
                    answer = response["answer"]
                    context_docs = response.get("context", [])
                    
                    st.markdown(answer)
                    
                    if context_docs:
                        with st.expander("📚 Источники (Контекст)"):
                            for doc in context_docs:
                                st.caption(f"**Модуль:** {doc.metadata.get('module', 'N/A')} | **Тема:** {doc.metadata.get('topic', 'N/A')}")
                    
                    log_interaction(prompt, answer, context_docs)
                    
                    # Escalation check
                    if "нет точной информации" in answer.lower() or "обратитесь к преподавателю" in answer.lower() or "в поддержку" in answer.lower():
                        add_escalation(active_student['username'], prompt, answer)
                        st.info("🔔 Ваш вопрос передан живому преподавателю. Ожидайте ответа.")
                    
                    # Save assistant message
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": answer,
                        "context": context_docs
                    })
                    save_chat_message(active_student['username'], "assistant", answer, context_docs)
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке запроса в чате: {e}", exc_info=True)
                    st.error(f"⚠️ Ошибка при обработке запроса: {str(e)}")

def render_student_hw_tab(active_student, schedule):
    st.header("📚 Мои задания")
    st.markdown("Здесь вы можете просмотреть свои задания и загрузить решения.")
    
    for task in schedule:
        with st.expander(f"📝 {task['title']} (Дедлайн: {task['deadline'][:10]})"):
            st.markdown(f"**Описание:** {task['description']}")
            st.markdown(f"**Требования:**\n{task['requirements']}")
            
            hw_file = st.file_uploader("Прикрепить файл решения", type=['py', 'zip', 'pdf', 'txt', 'docx'], key=f"up_{task['task_id']}")
            hw_comment = st.text_area("Комментарий к работе", key=f"com_{task['task_id']}")
            
            if st.button("🚀 Отправить на проверку", type="primary", key=f"btn_{task['task_id']}"):
                if hw_file:
                    with st.spinner("Проверка релевантности файла..."):
                        student_hw_dir = os.path.join(HOMEWORKS_DIR, active_student['username'], task['task_id'])
                        os.makedirs(student_hw_dir, exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_filename = f"{timestamp}_{hw_file.name}"
                        file_path = os.path.join(student_hw_dir, safe_filename)
                        
                        with open(file_path, "wb") as f:
                            f.write(hw_file.getbuffer())
                        
                        # Валидация
                        content = extract_text_from_file(file_path)
                        val_res = validate_homework_relevance(content, task['title'], task['description'])
                        
                        if val_res.startswith("NO"):
                            os.remove(file_path) # Удаляем нерелевантный файл
                            st.error(f"❌ Система отклонила файл. Причина: {val_res.replace('NO:', '').strip()}")
                        else:
                            if hw_comment:
                                with open(f"{file_path}.comment.txt", "w", encoding="utf-8") as f:
                                    f.write(f"Студент: {active_student['name']}\nВремя: {timestamp}\nКомментарий: {hw_comment}")
                            logger.info(f"Студент {active_student['username']} успешно загрузил ДЗ: {safe_filename}")
                            st.success("🎉 Ваше домашнее задание успешно отправлено! Ожидайте проверку.")
                            st.balloons()
                else:
                    st.warning("⚠️ Пожалуйста, прикрепите файл перед отправкой.")

def render_student_feedback_tab(active_student, schedule):
    st.header("📬 Мои оценки и отзывы")
    st.markdown("Здесь появляются проверенные преподавателем работы.")
    
    feedbacks = get_student_feedback(active_student['username'])
    if not feedbacks:
        st.info("📭 У вас пока нет проверенных работ.")
    else:
        for fb in feedbacks:
            with st.container():
                task_info = next((t for t in schedule if t['task_id'] == fb['task_id']), None)
                task_title = task_info['title'] if task_info else fb['task_id']
                
                st.markdown(f"### 📝 Задание: {task_title}")
                st.caption(f"📄 Файл: `{fb['filename']}` | 📅 Дата проверки: {fb['created_at']}")
                
                score_color = "🟢" if fb['score'] > 55 else "🔴"
                st.markdown(f"**Оценка:** {score_color} {fb['score']} / 100")
                
                st.info(fb['feedback_text'])
                st.divider()

def render_student_support_tab(active_student, student_unread):
    st.header("📨 Поддержка (Связь с преподавателем)")
    st.markdown("Здесь отображаются ваши вопросы, которые были переданы живому преподавателю.")
    
    if student_unread > 0:
        if st.button("✅ Отметить все новые сообщения как прочитанные", type="primary"):
            mark_student_read(active_student['username'])
            st.rerun()
            
    escalations = get_student_escalations(active_student['username'])
    if not escalations:
        st.info("У вас нет активных запросов к преподавателю.")
    else:
        for esc in escalations:
            status_icon = "🟢 Решен" if esc['status'] == "resolved" else "🟡 В работе"
            with st.expander(f"Запрос от {esc['created_at'][:16]} | Статус: {status_icon}"):
                st.markdown(f"**Ваш вопрос:** {esc['query']}")
                
                st.markdown("---")
                st.markdown("💬 **Чат с преподавателем:**")
                
                messages = get_support_messages(esc['id'])
                if not messages:
                    st.caption("Преподаватель пока не ответил на ваш запрос. Ожидайте.")
                    
                for msg in messages:
                    avatar = "🎓" if msg['sender_role'] == "Администратор" else "🧑‍💻"
                    with st.chat_message("assistant" if msg['sender_role'] == "Администратор" else "user", avatar=avatar):
                        st.markdown(msg['message'])
                
                if esc['status'] == 'active':
                    reply = st.text_input("Новое сообщение:", key=f"reply_student_{esc['id']}")
                    if st.button("Отправить", key=f"send_student_{esc['id']}"):
                        if reply:
                            add_support_message(esc['id'], "Студент", reply)
                            st.rerun()
                        else:
                            st.warning("Введите текст сообщения.")
                else:
                    st.info("Этот запрос закрыт. Если у вас появились новые вопросы, задайте их в чате с ИИ.")
