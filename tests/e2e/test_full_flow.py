import pytest
from playwright.sync_api import Page, expect
from tests.pages.login_page import LoginPage
from tests.pages.admin_page import AdminPage
from tests.pages.chat_page import ChatPage
import time

class TestFullFlow:
    """Полный E2E-набор тестов для LMS."""

    def test_admin_login_and_create_student(self, app_page: Page):
        """
        Сценарий: 
        1. Админ входит в систему.
        2. Админ переходит на вкладку студентов.
        3. Админ создает нового студента и получает доступы.
        4. Админ выходит из системы.
        """
        login_page = LoginPage(app_page)
        login_page.login_as_admin()
        
        # Проверяем, что вошли как админ
        expect(app_page.get_by_role("heading", name="Панель Админа")).to_be_visible()
        
        admin_page = AdminPage(app_page)
        admin_page.go_to_students_tab()
        
        # Создаем студента
        test_name = f"Test User {int(time.time())}"
        credentials = admin_page.create_student(test_name, "QA Automation")
        
        assert credentials["username"], "Логин не был сгенерирован"
        assert credentials["password"], "Пароль не был сгенерирован"
        
        # Выход
        admin_page.logout()
        expect(login_page.login_header).to_be_visible()
        
        # Сохраняем креды для следующего теста (в реальном проекте лучше через фикстуру)
        pytest.student_creds = credentials

    def test_student_login_and_rag_chat(self, app_page: Page):
        """
        Сценарий:
        1. Студент входит по сгенерированным данным.
        2. Студент задает вопрос по базе знаний (RAG).
        3. Студент задает вопрос вне базы (Эскалация).
        4. Студент очищает историю.
        """
        # Если первый тест не запускался, пропускаем
        if not hasattr(pytest, "student_creds"):
            pytest.skip("Нет данных тестового студента")
            
        creds = pytest.student_creds
        
        login_page = LoginPage(app_page)
        login_page.login(creds["username"], creds["password"])
        
        # Проверяем, что вошли как студент
        expect(app_page.get_by_role("heading", name="Профиль студента")).to_be_visible()
        
        chat_page = ChatPage(app_page)
        
        # --- Тест вопроса по базе знаний ---
        test_query_kb = "Что такое RAG?"
        chat_page.send_message(test_query_kb)
        
        response_kb = chat_page.get_last_message_text()
        assert len(response_kb) > 10, "Ответ слишком короткий"
        assert "ошибка" not in response_kb.lower(), "В ответе ошибка"
        
        # --- Тест вопроса ВНЕ базы знаний (Эскалация) ---
        test_query_out = "Как приготовить борщ?"
        chat_page.send_message(test_query_out)
        
        response_out = chat_page.get_last_message_text()
        # Проверяем, что сработала логика эскалации (в app.py проверяются эти фразы)
        escalation_triggered = (
            "нет точной информации" in response_out.lower() or 
            "обратитесь к преподавателю" in response_out.lower() or 
            "в поддержку" in response_out.lower()
        )
        assert escalation_triggered, "Вопрос вне базы знаний не вызвал эскалацию"
        
        # Проверяем появление плашки о передаче вопроса преподавателю
        expect(app_page.locator("div[data-testid='stAlert']").filter(has_text="Ваш вопрос передан живому преподавателю")).to_be_visible()

        # --- Тест очистки истории ---
        chat_page.clear_history()
        expect(chat_page.chat_messages).to_have_count(1)
