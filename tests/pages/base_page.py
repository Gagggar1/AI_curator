from playwright.sync_api import Page, Locator

class BasePage:
    """Базовый класс для всех Page Objects, содержит общие методы."""
    
    def __init__(self, page: Page):
        self.page = page

    def navigate(self, path: str) -> None:
        """Переход по указанному пути."""
        self.page.goto(path)
        self.page.wait_for_load_state("networkidle")

    def wait_for_element(self, locator: Locator, state: str = "visible", timeout: int = 5000) -> None:
        """Ожидание определенного состояния элемента."""
        locator.wait_for(state=state, timeout=timeout)
