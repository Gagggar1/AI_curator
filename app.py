import streamlit as st
import pandas as pd
import json
import os
from dotenv import load_dotenv

# Disable ChromaDB telemetry to prevent console warnings
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from src.logger import setup_logger
logger = setup_logger(__name__)

from src.config import LOG_FILE, HOMEWORKS_DIR, SCHEDULE_JSON
from src.db import (
    init_db, get_all_students, get_unread_admin_count, 
    get_unread_student_count, get_student_escalations, clear_chat_history
)
from src.agent import get_curator_chain
from src.ui.components import apply_custom_css, login_page
from src.ui.admin_dashboard import (
    render_admin_students_tab, render_admin_kb_tab, 
    render_admin_analytics_tab, render_admin_syllabus_tab, 
    render_admin_hw_tab, render_admin_escalations_tab
)
from src.ui.student_dashboard import (
    render_student_chat_tab, render_student_hw_tab, 
    render_student_feedback_tab, render_student_support_tab
)

def init_files():
    os.makedirs("data/analytics", exist_ok=True)
    os.makedirs("data/lms", exist_ok=True)
    os.makedirs(HOMEWORKS_DIR, exist_ok=True)
    
    if not os.path.exists(LOG_FILE):
        df = pd.DataFrame(columns=["timestamp", "query", "response", "topic_inferred"])
        df.to_csv(LOG_FILE, index=False)
        
    init_db()
    
    if not os.path.exists("chroma_db"):
        try:
            from src.rag import init_vector_db
            from src.config import KB_DIR
            logger.info("ChromaDB не найдена. Запуск первичной индексации...")
            init_vector_db(KB_DIR)
        except Exception as e:
            logger.error(f"Ошибка при первичной индексации: {e}")

def load_schedule():
    with open(SCHEDULE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    st.set_page_config(
        page_title="ИИ-Куратор | LMS",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    apply_custom_css()
    init_files()
    
    if not st.session_state.get("logged_in", False):
        login_page()
        return

    students = get_all_students()
    schedule = load_schedule()
    
    if "chain" not in st.session_state:
        st.session_state.chain = get_curator_chain()
        
    active_student = None
    if st.session_state.user_role == "Студент":
        active_student = next((s for s in students if s["id"] == st.session_state.active_student_id), None)
        
    with st.sidebar:
        if st.session_state.user_role == "Студент":
            st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=100)
            st.title("Профиль студента")
            
            if active_student:
                st.info(f"""
                👤 **Имя:** {active_student['name']}  
                📚 **Курс:** {active_student['course']}  
                🎓 **Уровень:** {active_student['level']}  
                📈 **Прогресс:** {active_student['progress']}%
                """)
                st.progress(active_student['progress'] / 100)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/320/320333.png", width=100)
            st.title("Панель Админа")
            st.success("Вы вошли как Администратор.")
            
            st.markdown("**👁️ Симуляция студента в чате:**")
            student_options = {s["id"]: f"{s['name']} ({s['course']})" for s in students}
            
            if not getattr(st.session_state, "active_student_id", None) in student_options:
                st.session_state.active_student_id = list(student_options.keys())[0] if student_options else None
                
            if student_options:
                selected_student_id = st.selectbox(
                    "Выберите студента для теста:", 
                    options=list(student_options.keys()), 
                    format_func=lambda x: student_options[x],
                    index=list(student_options.keys()).index(st.session_state.active_student_id)
                )
                st.session_state.active_student_id = selected_student_id
                active_student = next((s for s in students if s["id"] == st.session_state.active_student_id), None)
        
        st.divider()
        st.markdown("### 🛠 Управление")
        if st.button("🗑️ Очистить историю чата", use_container_width=True):
            if active_student:
                clear_chat_history(active_student['username'])
                if f"chat_loaded_{active_student['username']}" in st.session_state:
                    del st.session_state[f"chat_loaded_{active_student['username']}"]
                # Keep only the first welcome message
                if "messages" in st.session_state and len(st.session_state.messages) > 0:
                    st.session_state.messages = [st.session_state.messages[0]]
            st.rerun()
            
        if st.button("🚪 Выйти из системы", use_container_width=True):
            st.session_state.logged_in = False
            if "messages" in st.session_state:
                st.session_state.messages = []
            if "chain" in st.session_state:
                del st.session_state.chain
            st.rerun()

    if st.session_state.user_role == "Администратор":
        admin_unread = get_unread_admin_count()
        esc_tab_name = f"📨 Запросы 🔴 ({admin_unread})" if admin_unread > 0 else "📨 Запросы"
        
        tabs = st.tabs(["💬 Чат", "👥 Студенты (Доступы)", "📁 База знаний", "📊 Аналитика", "📚 Программа", "📥 Проверка ДЗ", esc_tab_name])
        tab_chat, tab_students, tab_kb, tab_analytics, tab_syllabus, tab_hw_admin, tab_escalations = tabs
        
        with tab_chat:
            render_student_chat_tab(active_student)
        with tab_students:
            render_admin_students_tab(students)
        with tab_kb:
            render_admin_kb_tab()
        with tab_analytics:
            render_admin_analytics_tab()
        with tab_syllabus:
            render_admin_syllabus_tab(schedule)
        with tab_hw_admin:
            render_admin_hw_tab(schedule)
        with tab_escalations:
            render_admin_escalations_tab(admin_unread)
            
    else:
        student_escalations = get_student_escalations(active_student['username']) if active_student else []
        student_unread = get_unread_student_count(active_student['username']) if active_student else 0
        
        if student_escalations:
            support_tab_name = f"📨 Поддержка 🔴 ({student_unread})" if student_unread > 0 else "📨 Поддержка"
            tabs = st.tabs(["💬 Чат с ИИ", "📚 Мои задания", "📬 Мои оценки", support_tab_name])
            tab_chat, tab_hw_student, tab_feedback, tab_support = tabs
            
            with tab_chat:
                render_student_chat_tab(active_student)
            with tab_hw_student:
                render_student_hw_tab(active_student, schedule)
            with tab_feedback:
                render_student_feedback_tab(active_student, schedule)
            with tab_support:
                render_student_support_tab(active_student, student_unread)
        else:
            tabs = st.tabs(["💬 Чат с ИИ", "📚 Мои задания", "📬 Мои оценки"])
            tab_chat, tab_hw_student, tab_feedback = tabs
            
            with tab_chat:
                render_student_chat_tab(active_student)
            with tab_hw_student:
                render_student_hw_tab(active_student, schedule)
            with tab_feedback:
                render_student_feedback_tab(active_student, schedule)

if __name__ == "__main__":
    main()
