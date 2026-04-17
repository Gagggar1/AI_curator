from playwright.sync_api import Page, expect
from .base_page import BasePage

class AdminPage(BasePage):
    """Page Object для панели администратора."""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.students_tab = page.get_by_role("tab", name="👥 Студенты (Доступы)")
        self.add_student_expander = page.locator("div[data-testid='stExpander']").filter(has_text="Создать профиль студента")
        self.name_input = page.get_by_label("ФИО студента")
        self.course_input = page.get_by_label("Курс (например, Python Developer)")
        self.save_button = page.get_by_role("button", name="Сгенерировать доступы и сохранить")
        
    def go_to_students_tab(self):
        self.students_tab.click()
        
    def create_student(self, name: str, course: str) -> dict:
        """Создает студента и возвращает его логин и пароль."""
        self.add_student_expander.click()
        self.name_input.fill(name)
        self.course_input.fill(course)
        self.save_button.click()
        
        # Ищем сообщение об успехе
        success_msg = self.page.locator("div[data-testid='stMarkdownContainer']").filter(has_text=f"Студент {name} успешно добавлен!")
        success_msg.wait_for(state="visible", timeout=10000)
        
        # Парсим логин и пароль из информационного блока
        info_block = self.page.locator("div[data-testid='stAlert']").filter(has_text="Передайте эти данные студенту")
        text = info_block.inner_text()
        
        # Простой парсинг (в тексте будет "Логин: user1234 Пароль: xxxx")
        import re
        login_match = re.search(r"Логин:\s*`?([a-zA-Z0-9_]+)`?", text)
        pass_match = re.search(r"Пароль:\s*`?([a-zA-Z0-9_]+)`?", text)
        
        return {
            "username": login_match.group(1) if login_match else "",
            "password": pass_match.group(1) if pass_match else ""
        }
    
    def logout(self):
        self.page.get_by_role("button", name="🚪 Выйти из системы").click()
