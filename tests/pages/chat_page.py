from playwright.sync_api import Page, expect
from .base_page import BasePage

class ChatPage(BasePage):
    """Page Object для чата с ИИ-Куратором."""
    
    def __init__(self, page: Page):
        super().__init__(page)
        # В Streamlit поле ввода чата находится в специальном контейнере
        self.chat_input = page.locator("div[data-testid='stChatInput'] textarea")
        # Выбираем только видимые сообщения
        self.chat_messages = page.locator("div[data-testid='stChatMessage']:visible")
        self.clear_history_button = page.get_by_role("button", name="🗑️ Очистить историю чата")

    def send_message(self, text: str) -> None:
        """Отправка сообщения в чат."""
        # Ждем, пока поле ввода станет доступным
        self.chat_input.wait_for(state="visible", timeout=10000)
        self.chat_input.fill(text)
        self.chat_input.press("Enter")
        
        # Ждем, пока появится индикатор загрузки (spinner) и исчезнет
        # Streamlit обычно показывает элемент с data-testid="stSpinner" или блокирует UI
        try:
            self.page.locator("div[data-testid='stSpinner']").wait_for(state="visible", timeout=2000)
            self.page.locator("div[data-testid='stSpinner']").wait_for(state="hidden", timeout=30000)
        except:
            # Если спиннер не поймали (слишком быстро), ждем просто появления нового сообщения
            pass
            
        # Ждем, пока последнее сообщение (ответ ассистента) полностью отрендерится
        # Ассистент имеет иконку 🎓
        self.page.locator("div[data-testid='stChatMessage']").filter(has_text="🎓").last.wait_for(state="visible", timeout=30000)

    def get_last_message_text(self) -> str:
        """Получение текста последнего видимого сообщения в чате."""
        # Берем последнее сообщение
        last_msg = self.chat_messages.last
        last_msg.wait_for(state="visible", timeout=10000)
        return last_msg.inner_text()

    def clear_history(self) -> None:
        """Очистка истории чата."""
        self.clear_history_button.click()
        # Ожидаем, что останется только одно приветственное сообщение
        expect(self.chat_messages).to_have_count(1, timeout=10000)
