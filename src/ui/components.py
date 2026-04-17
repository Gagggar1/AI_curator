import streamlit as st
from src.db import verify_student
from src.config import ADMIN_USERNAME, ADMIN_PASSWORD
from src.logger import setup_logger

logger = setup_logger(__name__)

def apply_custom_css():
    st.markdown("""
        <style>
        .stApp { background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        div[data-testid="metric-container"], div.stAlert, .login-box {
            background: rgba(255, 255, 255, 0.6);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 15px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        }
        .stButton>button {
            border-radius: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            font-weight: 600;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            color: white;
            border-color: transparent;
        }
        .stChatMessage {
            background: rgba(255, 255, 255, 0.8);
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            border: 1px solid rgba(255,255,255,0.5);
        }
        [data-testid="stSidebar"] {
            background-color: rgba(248, 249, 250, 0.9);
            backdrop-filter: blur(10px);
            border-right: 1px solid rgba(0,0,0,0.05);
        }
        @media (prefers-color-scheme: dark) {
            .stApp { background: linear-gradient(135deg, #1e1e24 0%, #0a0a0a 100%); }
            div[data-testid="metric-container"], div.stAlert, .stChatMessage, .login-box {
                background: rgba(30, 30, 30, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.05);
                color: #e0e0e0;
            }
            [data-testid="stSidebar"] { background-color: rgba(20, 20, 20, 0.9); }
        }
        </style>
    """, unsafe_allow_html=True)

def login_page():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=80)
        st.title("Вход в LMS")
        st.markdown("Пожалуйста, авторизуйтесь для доступа к платформе.")
        
        with st.form("login_form"):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти", use_container_width=True)
            
            if submitted:
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    logger.info("Успешный вход: Администратор")
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Администратор"
                    st.rerun()
                else:
                    student = verify_student(username, password)
                    if student:
                        logger.info(f"Успешный вход: Студент {username}")
                        st.session_state.logged_in = True
                        st.session_state.user_role = "Студент"
                        st.session_state.active_student_id = student["id"]
                        st.rerun()
                    else:
                        logger.warning(f"Неудачная попытка входа для логина: {username}")
                        st.error("❌ Неверный логин или пароль")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.info(f"💡 Подсказка: Админ по умолчанию: **{ADMIN_USERNAME}** / **{ADMIN_PASSWORD}** (можно изменить в .env)")
