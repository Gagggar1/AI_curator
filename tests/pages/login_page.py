from playwright.sync_api import Page, expect
from .base_page import BasePage
import os

class LoginPage(BasePage):
    """Page Object для страницы авторизации."""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.username_input = page.get_by_label("Логин")
        self.password_input = page.get_by_label("Пароль")
        self.login_button = page.get_by_role("button", name="Войти")
        self.login_header = page.get_by_role("heading", name="Вход в LMS")

    def login_as_admin(self) -> None:
        """Вход под администратором."""
        admin_user = os.getenv("ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin")
        self.login(admin_user, admin_pass)
        
    def login(self, username: str, password: str) -> None:
        """Общий метод входа."""
        self.login_header.wait_for(state="visible", timeout=10000)
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
        
        # Ожидаем исчезновения формы логина
        self.login_header.wait_for(state="hidden", timeout=10000)
