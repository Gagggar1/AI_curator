import os
import json
import logging

# Disable ChromaDB telemetry to prevent console warnings
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.logger import setup_logger

logger = setup_logger(__name__)

def load_knowledge_base(directory: str) -> list[Document]:
    documents = []
    
    # Проходим по всем файлам в директории
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        try:
            if filename.endswith('.json'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    if item.get("type") == "faq":
                        content = f"Q: {item.get('question')}\nA: {item.get('answer')}"
                    else:
                        content = item.get("content", "")
                        
                    metadata = {
                        "source": filename,
                        "topic": item.get("topic", "unknown"),
                        "module": item.get("module", "general"),
                        "type": item.get("type", "document")
                    }
                    documents.append(Document(page_content=content, metadata=metadata))
                    
            elif filename.endswith('.pdf'):
                loader = PyPDFLoader(filepath)
                docs = loader.load()
                for d in docs:
                    d.metadata["type"] = "pdf"
                    d.metadata["source"] = filename
                    d.metadata["module"] = "general"
                    d.metadata["topic"] = "unknown"
                documents.extend(docs)
                
            elif filename.endswith('.docx'):
                loader = Docx2txtLoader(filepath)
                docs = loader.load()
                for d in docs:
                    d.metadata["type"] = "docx"
                    d.metadata["source"] = filename
                    d.metadata["module"] = "general"
                    d.metadata["topic"] = "unknown"
                documents.extend(docs)
                
            elif filename.endswith('.txt'):
                loader = TextLoader(filepath, encoding='utf-8')
                docs = loader.load()
                for d in docs:
                    d.metadata["type"] = "txt"
                    d.metadata["source"] = filename
                    d.metadata["module"] = "general"
                    d.metadata["topic"] = "unknown"
                documents.extend(docs)
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла {filename}: {e}")

    # Разбиваем большие документы на части (чанки) для лучшего поиска
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    
    return split_docs

def init_vector_db(kb_dir: str = "data/kb", persist_directory: str = "chroma_db"):
    # Загружаем и разбиваем все документы из папки
    docs = load_knowledge_base(kb_dir)
    
    if not docs:
        logger.warning("Не найдено документов для индексации!")
        return None
        
    # Load embedding model from env
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Initialize embeddings
    embeddings = OpenAIEmbeddings(model=embedding_model)
    
    # Очищаем старую коллекцию, чтобы избежать дубликатов (вместо удаления папки)
    try:
        old_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        old_db.delete_collection()
    except Exception as e:
        logger.warning(f"Не удалось удалить старую коллекцию: {e}")
    
    # Create and persist vectorstore
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    return vectorstore

def get_retriever(persist_directory: str = "chroma_db"):
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embeddings = OpenAIEmbeddings(model=embedding_model)
    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 4})

if __name__ == "__main__":
    # Test indexing
    from dotenv import load_dotenv
    load_dotenv()
    
    logger.info("Начало индексации базы знаний (все форматы)...")
    try:
        init_vector_db("data/kb")
        logger.info("Индексация успешно завершена!")
    except Exception as e:
        logger.error(f"Ошибка во время индексации: {e}")
