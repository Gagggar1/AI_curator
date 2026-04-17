import streamlit as st
import pandas as pd
import os
import random
from datetime import datetime
from src.config import LOG_FILE, HOMEWORKS_DIR, KB_DIR
from src.db import (
    get_all_students, add_student, reset_student_progress,
    get_active_escalations, mark_admin_read, get_support_messages,
    add_support_message, resolve_escalation, get_student_feedback,
    add_or_update_feedback, update_student_progress,
    clear_chat_history, delete_student_escalations, delete_single_escalation
)
from src.services.homework_service import check_homework_with_ai
from src.logger import setup_logger

logger = setup_logger(__name__)

def generate_password(length=8):
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def render_admin_students_tab(students):
    st.header("👥 Управление студентами и доступами")
    st.markdown("Добавляйте новых студентов. Система автоматически сгенерирует для них логин и пароль.")
    
    with st.expander("➕ Создать профиль студента", expanded=False):
        with st.form("add_student_form"):
            new_name = st.text_input("ФИО студента")
            new_course = st.text_input("Курс (например, Python Developer)")
            new_level = st.selectbox("Уровень", ["Начинающий", "Средний", "Продвинутый"])
            new_progress = st.slider("Текущий прогресс (%)", 0, 100, 0)
            
            if st.form_submit_button("Сгенерировать доступы и сохранить"):
                if new_name and new_course:
                    new_id = str(int(datetime.now().timestamp()))
                    new_username = f"user{random.randint(1000, 9999)}"
                    new_password = generate_password(8)
                    
                    add_student(new_id, new_name, new_course, new_level, new_progress, new_username, new_password)
                    st.success(f"✅ Студент {new_name} успешно добавлен!")
                    st.info(f"**Передайте эти данные студенту:**\n\nЛогин: `{new_username}`\n\nПароль: `{new_password}`")
                else:
                    st.error("Заполните Имя и Курс!")
    
    st.subheader("База студентов (Доступы)")
    # Refresh students list after potential addition
    students = get_all_students()
    df_students = pd.DataFrame(students)
    if not df_students.empty:
        # We don't show the hashed password in the table, it's useless now
        st.dataframe(df_students[['name', 'course', 'level', 'progress', 'username']], use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("Сброс прогресса")
    reset_user = st.selectbox("Выберите студента для сброса прогресса", [s['username'] for s in students])
    if st.button("⚠️ Сбросить прогресс студента до 0%"):
        reset_student_progress(reset_user)
        st.success(f"Прогресс студента {reset_user} успешно сброшен!")
        st.rerun()

    st.divider()
    st.subheader("🗑️ Очистка истории (Откат)")
    st.markdown("Полное удаление истории переписки студента. Изменения необратимы и отразятся как у администратора, так и у студента.")
    
    clear_user = st.selectbox("Выберите студента для очистки истории", [s['username'] for s in students], key="clear_user_select")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Удалить чат с ИИ", use_container_width=True):
            clear_chat_history(clear_user)
            # Очищаем кэш сессии
            if f"chat_loaded_{clear_user}" in st.session_state:
                del st.session_state[f"chat_loaded_{clear_user}"]
            if "messages" in st.session_state:
                st.session_state.messages = []
            st.success(f"✅ Чат с ИИ для студента {clear_user} очищен!")
            
    with col2:
        if st.button("Удалить обращения в поддержку", use_container_width=True):
            delete_student_escalations(clear_user)
            st.success(f"✅ Все обращения в поддержку для {clear_user} удалены!")

def render_admin_kb_tab():
    st.header("📁 Управление базой знаний")
    st.markdown("Загружайте новые лекции, методички и FAQ. Поддерживаемые форматы: **PDF, DOCX, TXT, JSON**.")
    
    uploaded_files = st.file_uploader("Выберите файлы для загрузки", accept_multiple_files=True, type=['pdf', 'docx', 'txt', 'json'])
    
    if st.button("💾 Сохранить и проиндексировать базу", type="primary"):
        if uploaded_files:
            with st.spinner("Сохранение файлов и обновление базы знаний... Это может занять несколько секунд."):
                os.makedirs(KB_DIR, exist_ok=True)
                for file in uploaded_files:
                    with open(os.path.join(KB_DIR, file.name), "wb") as f:
                        f.write(file.getbuffer())
                try:
                    from src.rag import init_vector_db
                    if "chain" in st.session_state:
                        del st.session_state.chain
                    init_vector_db(KB_DIR)
                    logger.info("База знаний успешно обновлена администратором.")
                    st.success("✅ База знаний успешно обновлена и проиндексирована!")
                except Exception as e:
                    logger.error(f"Ошибка при индексации базы знаний: {e}", exc_info=True)
                    st.error(f"❌ Ошибка при индексации: {e}")
        else:
            st.warning("⚠️ Пожалуйста, выберите хотя бы один файл для загрузки.")
            
    st.divider()
    st.subheader("Текущие файлы в базе знаний:")
    try:
        kb_files = os.listdir(KB_DIR)
        if kb_files:
            for f in kb_files:
                st.text(f"📄 {f}")
        else:
            st.info("База знаний пуста.")
    except FileNotFoundError:
        st.info("Папка базы знаний еще не создана.")

def render_admin_analytics_tab():
    st.header("📊 Аналитика обращений студентов")
    try:
        df = pd.read_csv(LOG_FILE)
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            total_queries = len(df)
            today_queries = len(df[df['timestamp'].str.startswith(datetime.now().strftime("%Y-%m-%d"))])
            top_topic = df['topic_inferred'].mode()[0] if not df.empty else "Нет данных"
            
            col1.metric("Всего вопросов", total_queries, delta="За все время")
            col2.metric("Вопросов сегодня", today_queries, delta=f"{today_queries} новых", delta_color="normal")
            col3.metric("Самая частая тема", top_topic.capitalize())
            
            st.divider()
            col_chart, col_table = st.columns([1, 1])
            with col_chart:
                st.subheader("Распределение по темам")
                topic_counts = df["topic_inferred"].value_counts().reset_index()
                topic_counts.columns = ['Тема', 'Количество']
                st.bar_chart(topic_counts.set_index('Тема'))
            with col_table:
                st.subheader("Последние запросы")
                recent_df = df[['timestamp', 'topic_inferred', 'query']].tail(10).sort_values(by="timestamp", ascending=False)
                recent_df.columns = ['Дата/Время', 'Тема', 'Вопрос']
                st.dataframe(recent_df, use_container_width=True, hide_index=True)
        else:
            st.info("📭 Пока нет данных для аналитики.")
    except Exception as e:
        st.error(f"Ошибка загрузки аналитики: {e}")

def render_admin_syllabus_tab(schedule):
    st.header("📚 Программа курса (Задания)")
    st.markdown("Здесь отображаются все активные задания и уроки для студентов.")
    for task in schedule:
        with st.expander(f"📝 {task['title']} (Дедлайн: {task['deadline'][:10]})"):
            st.markdown(f"**Модуль:** {task['module']}")
            st.markdown(f"**Описание:** {task['description']}")
            st.markdown(f"**Требования:**\n{task['requirements']}")
            st.markdown(f"**Статус:** {task['status']}")

def render_admin_hw_tab(schedule):
    st.header("📥 Проверка домашних заданий")
    st.markdown("Здесь отображаются файлы, загруженные студентами к конкретным заданиям.")
    
    try:
        hw_folders = os.listdir(HOMEWORKS_DIR)
        if not hw_folders:
            st.info("Пока никто не сдал домашнее задание.")
        else:
            for student_folder in hw_folders:
                student_path = os.path.join(HOMEWORKS_DIR, student_folder)
                if os.path.isdir(student_path):
                    for task_folder in os.listdir(student_path):
                        task_path = os.path.join(student_path, task_folder)
                        if os.path.isdir(task_path):
                            files = os.listdir(task_path)
                            actual_files = [f for f in files if not f.endswith('.comment.txt')]
                            
                            # Находим инфу о задании
                            task_info = next((t for t in schedule if t['task_id'] == task_folder), None)
                            task_title = task_info['title'] if task_info else task_folder
                            task_desc = task_info['description'] if task_info else ""
                            
                            if actual_files:
                                with st.expander(f"📁 Студент: {student_folder} | Задание: {task_title}"):
                                    for file in actual_files:
                                        st.markdown(f"### 📄 {file}")
                                        file_path = os.path.join(task_path, file)
                                        
                                        with open(file_path, "rb") as f:
                                            st.download_button(
                                                label="⬇️ Скачать файл",
                                                data=f,
                                                file_name=file,
                                                mime="application/octet-stream",
                                                key=f"dl_{student_folder}_{task_folder}_{file}"
                                            )
                                        
                                        comment_file = f"{file}.comment.txt"
                                        if comment_file in files:
                                            with open(os.path.join(task_path, comment_file), "r", encoding="utf-8") as cf:
                                                st.info(f"**Комментарий студента:**\n{cf.read().split('Комментарий: ')[-1]}")
                                        
                                        existing_feedbacks = get_student_feedback(student_folder)
                                        existing_fb = next((fb for fb in existing_feedbacks if fb['task_id'] == task_folder), None)
                                        
                                        default_fb_text = existing_fb['feedback_text'] if existing_fb else ""
                                        default_score = existing_fb['score'] if existing_fb else 0
                                        
                                        if st.button("🤖 Сгенерировать отзыв ИИ (Без оценки)", key=f"ai_btn_{student_folder}_{task_folder}_{file}"):
                                            with st.spinner("ИИ проверяет работу..."):
                                                ai_feedback = check_homework_with_ai(file_path, task_title, task_desc)
                                                st.session_state[f"fb_text_{student_folder}_{task_folder}_{file}"] = ai_feedback
                                                st.rerun()
                                        
                                        draft_text = st.session_state.get(f"fb_text_{student_folder}_{task_folder}_{file}", default_fb_text)
                                        draft_score = st.session_state.get(f"score_{student_folder}_{task_folder}_{file}", default_score)
                                        
                                        score_input = st.number_input("Оценка (0-100):", min_value=0, max_value=100, value=draft_score, key=f"score_input_{student_folder}_{task_folder}_{file}")
                                        feedback_text = st.text_area(
                                            "Обратная связь для студента:", 
                                            value=draft_text,
                                            key=f"fb_input_{student_folder}_{task_folder}_{file}", 
                                            height=200
                                        )
                                        
                                        if st.button("📤 Отправить / Обновить отзыв", key=f"send_{student_folder}_{task_folder}_{file}", type="primary"):
                                            if feedback_text:
                                                old_score = add_or_update_feedback(student_folder, task_folder, file, feedback_text, score_input)
                                                
                                                progress_changed = False
                                                if old_score is None:
                                                    if score_input > 55:
                                                        update_student_progress(student_folder, 15)
                                                        progress_changed = True
                                                else:
                                                    if old_score <= 55 and score_input > 55:
                                                        update_student_progress(student_folder, 15)
                                                        progress_changed = True
                                                    elif old_score > 55 and score_input <= 55:
                                                        update_student_progress(student_folder, -15)
                                                        progress_changed = True
                                                
                                                st.success(f"✅ Отзыв сохранен! Оценка: {score_input}/100.")
                                                if progress_changed:
                                                    st.info("📈 Прогресс студента был пересчитан.")
                                            else:
                                                st.warning("⚠️ Напишите отзыв перед отправкой.")
                                        st.divider()
    except FileNotFoundError:
        st.info("Папка с домашними заданиями еще не создана.")

def render_admin_escalations_tab(admin_unread):
    st.header("📨 Запросы к преподавателю")
    st.markdown("Здесь отображаются вопросы студентов, на которые ИИ-куратор не смог найти ответ в базе знаний.")
    
    if admin_unread > 0:
        if st.button("✅ Отметить все новые сообщения как прочитанные", type="primary"):
            mark_admin_read()
            st.rerun()
            
    escalations = get_active_escalations()
    if not escalations:
        st.success("🎉 Нет новых запросов! ИИ справляется отлично.")
    else:
        for esc in escalations:
            with st.container():
                st.warning(f"**Студент:** {esc['student_username']} | **Время:** {esc['created_at']}")
                st.markdown(f"**Вопрос студента:** {esc['query']}")
                st.caption(f"**Ответ ИИ:** {esc['ai_response']}")
                
                st.markdown("---")
                st.markdown("💬 **Чат со студентом:**")
                
                messages = get_support_messages(esc['id'])
                for msg in messages:
                    avatar = "🎓" if msg['sender_role'] == "Администратор" else "🧑‍💻"
                    with st.chat_message("assistant" if msg['sender_role'] == "Администратор" else "user", avatar=avatar):
                        st.markdown(msg['message'])
                
                reply = st.text_input("Ваш ответ:", key=f"reply_admin_{esc['id']}")
                col_send, col_resolve, col_delete = st.columns([1, 1, 1])
                with col_send:
                    if st.button("Отправить ответ", key=f"send_admin_{esc['id']}"):
                        if reply:
                            add_support_message(esc['id'], "Администратор", reply)
                            st.rerun()
                        else:
                            st.warning("Введите текст ответа.")
                with col_resolve:
                    if st.button("✅ Отметить как решенное", key=f"resolve_{esc['id']}", type="primary"):
                        resolve_escalation(esc['id'])
                        st.rerun()
                with col_delete:
                    if st.button("🗑️ Удалить запрос", key=f"delete_{esc['id']}"):
                        delete_single_escalation(esc['id'])
                        st.rerun()
                st.divider()
