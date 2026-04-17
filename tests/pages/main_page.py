from playwright.sync_api import Page, expect
from .base_page import BasePage

class MainPage(BasePage):
    """
    Page Object для главной страницы приложения (после авторизации).
    """
    
    def __init__(self, page: Page):
        super().__init__(page)
        # Локаторы, адаптированные под Streamlit интерфейс из app.py
        self.chat_input = page.get_by_placeholder("Напишите ваш вопрос здесь...")
        self.chat_messages = page.locator(".stChatMessage")
        self.clear_history_button = page.get_by_role("button", name="🗑️ Очистить историю чата")

    def send_message(self, text: str) -> None:
        """Отправка сообщения в чат."""
        self.chat_input.fill(text)
        self.chat_input.press("Enter")
        
        # Ожидаем, пока появится ответ от ассистента (индикатор загрузки Streamlit исчезнет)
        # В Streamlit во время генерации ответа обычно крутится спиннер или статус
        self.page.locator(".stSpinner").wait_for(state="hidden", timeout=30000)
        # Также ждем, пока появится новое сообщение от ассистента
        self.chat_messages.last.wait_for(state="visible")

    def get_last_message_text(self) -> str:
        """Получение текста последнего сообщения в чате."""
        self.chat_messages.last.wait_for(state="visible")
        return self.chat_messages.last.inner_text()

    def clear_history(self) -> None:
        """Очистка истории чата."""
        self.clear_history_button.click()
        # Ожидаем, что останется только одно приветственное сообщение (как в коде app.py)
        expect(self.chat_messages).to_have_count(1, timeout=10000)
