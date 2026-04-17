import os
import zipfile
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.config import LLM_MODEL
from src.logger import setup_logger

logger = setup_logger(__name__)

def extract_text_from_file(filepath):
    content = ""
    if filepath.endswith('.py') or filepath.endswith('.txt') or filepath.endswith('.csv') or filepath.endswith('.md'):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    elif filepath.endswith('.pdf'):
        loader = PyPDFLoader(filepath)
        docs = loader.load()
        content = "\n".join([d.page_content for d in docs])
    elif filepath.endswith('.docx'):
        loader = Docx2txtLoader(filepath)
        docs = loader.load()
        content = "\n".join([d.page_content for d in docs])
    elif filepath.endswith('.zip'):
        try:
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    # Пропускаем директории и скрытые системные файлы (например, от macOS)
                    if file_info.is_dir() or file_info.filename.startswith('__MACOSX') or '.DS_Store' in file_info.filename:
                        continue
                    
                    # Читаем только файлы с кодом и текстом
                    valid_exts = ('.py', '.txt', '.md', '.csv', '.json', '.html', '.css', '.js', '.sql')
                    if file_info.filename.lower().endswith(valid_exts):
                        try:
                            with zip_ref.open(file_info) as f:
                                file_content = f.read().decode('utf-8')
                                content += f"\n\n--- Файл: {file_info.filename} ---\n\n"
                                content += file_content
                        except UnicodeDecodeError:
                            logger.warning(f"Не удалось декодировать файл {file_info.filename} как UTF-8")
                        except Exception as e:
                            logger.error(f"Ошибка чтения файла {file_info.filename} из архива: {e}")
        except Exception as e:
            logger.error(f"Ошибка при открытии zip-архива {filepath}: {e}")
            
    return content

def validate_homework_relevance(content, task_title, task_desc):
    try:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Ты валидатор домашних заданий. Проверь, относится ли присланный текст к заданию. Задание: '{title}'. Описание: '{desc}'. Если текст вообще не из этой темы (например, прислали HTML вместо SQL, или Git вместо Python), ответь 'NO: <причина>'. Если работа похожа на правду или пустая, ответь 'YES'."),
            ("human", "Текст работы:\n{content}")
        ])
        chain = prompt | llm
        res = chain.invoke({"title": task_title, "desc": task_desc, "content": content[:5000]})
        return res.content
    except Exception as e:
        logger.error(f"Ошибка API при валидации ДЗ: {e}")
        return "YES" # Пропускаем при ошибках API

def check_homework_with_ai(filepath, task_title, task_desc):
    try:
        content = extract_text_from_file(filepath)
        if not content.strip():
            return "Файл пуст или текст не удалось извлечь."

        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.2)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Ты опытный IT-преподаватель. Твоя задача — проверить домашнее задание студента по теме '{title}'. Описание задания: {desc}. Проанализируй код, укажи на ошибки, похвали за хорошие решения, дай рекомендации.\n\nВНИМАНИЕ: НЕ ВЫСТАВЛЯЙ ОЦЕНКУ И НЕ ПИШИ БАЛЛЫ (это делает человек-администратор). Просто напиши качественный текстовый отзыв."),
            ("human", "Вот мое домашнее задание:\n\n{content}")
        ])
        chain = prompt | llm
        response = chain.invoke({"title": task_title, "desc": task_desc, "content": content[:10000]})
        return response.content
    except Exception as e:
        logger.error(f"Ошибка API при проверке ДЗ ИИ: {e}")
        return f"Ошибка при проверке ИИ: {e}"
