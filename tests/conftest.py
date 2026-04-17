import os
import pytest
from playwright.sync_api import Page, expect
from dotenv import load_dotenv
import sqlite3
import shutil

load_dotenv()

@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:8501")

@pytest.fixture(scope="function")
def clean_state():
    """
    Подготовка чистого состояния. 
    В идеале здесь нужно использовать тестовую БД.
    Для E2E мы просто почистим кэш браузера между тестами (Playwright делает это сам для новых контекстов).
    """
    print("\n[Setup] Подготовка чистого состояния...")
    yield
    print("\n[Teardown] Очистка тестовых данных...")

@pytest.fixture
def app_page(page: Page, base_url: str, clean_state) -> Page:
    """Открывает главную страницу."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    return page
