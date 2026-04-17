import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str) -> logging.Logger:
    """
    Настраивает и возвращает логгер с выводом в консоль и ротацией файлов.
    """
    logger = logging.getLogger(name)
    
    # Предотвращаем дублирование обработчиков, если логгер уже был создан
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Создаем директорию для логов, если ее нет
        os.makedirs("data/logs", exist_ok=True)
        
        # 1. File Handler (Ротация файлов: максимум 5 МБ на файл, храним 3 резервные копии)
        file_handler = RotatingFileHandler(
            "data/logs/app.log", 
            maxBytes=5 * 1024 * 1024, 
            backupCount=3, 
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # 2. Console Handler (Вывод в терминал)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Добавляем обработчики к логгеру
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Подавляем лишний шум от сторонних библиотек
        logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
    return logger
