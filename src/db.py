import sqlite3
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
from src.logger import setup_logger
from src.config import DB_PATH, STUDENTS_JSON

logger = setup_logger(__name__)

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            course TEXT NOT NULL,
            level TEXT NOT NULL,
            progress INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_username TEXT NOT NULL,
            filename TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_username TEXT NOT NULL,
            query TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escalation_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(escalation_id) REFERENCES escalations(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            context_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE feedback ADD COLUMN score INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute('ALTER TABLE feedback ADD COLUMN task_id TEXT DEFAULT "unknown"')
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute('ALTER TABLE escalations ADD COLUMN is_read_by_admin INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute('ALTER TABLE support_messages ADD COLUMN is_read INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    
    cursor.execute('SELECT COUNT(*) FROM students')
    if cursor.fetchone()[0] == 0 and os.path.exists(STUDENTS_JSON):
        with open(STUDENTS_JSON, "r", encoding="utf-8") as f:
            students = json.load(f)
            for s in students:
                add_student(
                    s['id'], 
                    s['name'], 
                    s['course'], 
                    s['level'], 
                    s['progress'], 
                    s.get('username', f"student_{s['id']}"), 
                    s.get('password', 'pass123')
                )
    
    cursor.execute('SELECT COUNT(*) FROM students')
    if cursor.fetchone()[0] == 0:
        add_student("1", "Алексей С.", "Python Developer", "Начинающий", 35, "student1", "password123")
        add_student("2", "Елена В.", "FastAPI Backend", "Продвинутый", 85, "student2", "password123")
        
    conn.close()

def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def verify_student(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    if row and check_password_hash(row['password'], password):
        return dict(row)
    return None

def add_student(student_id, name, course, level, progress, username, password):
    conn = get_connection()
    cursor = conn.cursor()
    hashed_password = generate_password_hash(password)
    try:
        cursor.execute('''
            INSERT INTO students (id, name, course, level, progress, username, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, name, course, level, progress, username, hashed_password))
        conn.commit()
        logger.info(f"Добавлен новый студент: {username} ({name})")
    except sqlite3.IntegrityError:
        logger.warning(f"Попытка добавить дубликат студента: {username}")
    finally:
        conn.close()

def add_or_update_feedback(student_username, task_id, filename, feedback_text, score):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT score FROM feedback WHERE student_username = ? AND task_id = ?', (student_username, task_id))
    row = cursor.fetchone()
    old_score = row['score'] if row else None
    
    if row:
        cursor.execute('''
            UPDATE feedback 
            SET feedback_text = ?, score = ?, filename = ?, created_at = CURRENT_TIMESTAMP
            WHERE student_username = ? AND task_id = ?
        ''', (feedback_text, score, filename, student_username, task_id))
        logger.info(f"Обновлен отзыв для студента {student_username} (Задание: {task_id}, Оценка: {score})")
    else:
        cursor.execute('''
            INSERT INTO feedback (student_username, task_id, filename, feedback_text, score)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_username, task_id, filename, feedback_text, score))
        logger.info(f"Добавлен новый отзыв для студента {student_username} (Задание: {task_id}, Оценка: {score})")
        
    conn.commit()
    conn.close()
    return old_score

def get_student_feedback(student_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM feedback WHERE student_username = ? ORDER BY created_at DESC', (student_username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_student_progress(username, added_progress):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT progress FROM students WHERE username = ?', (username,))
    row = cursor.fetchone()
    if row:
        current_progress = row['progress']
        new_progress = max(0, min(100, current_progress + added_progress))
        cursor.execute('UPDATE students SET progress = ? WHERE username = ?', (new_progress, username))
        conn.commit()
    conn.close()

def reset_student_progress(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE students SET progress = 0 WHERE username = ?', (username,))
    conn.commit()
    conn.close()

def add_escalation(student_username, query, ai_response):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO escalations (student_username, query, ai_response)
        VALUES (?, ?, ?)
    ''', (student_username, query, ai_response))
    conn.commit()
    conn.close()

def get_active_escalations():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM escalations WHERE status = "active" ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def resolve_escalation(escalation_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE escalations SET status = "resolved" WHERE id = ?', (escalation_id,))
    conn.commit()
    conn.close()
    logger.info(f"Эскалация #{escalation_id} отмечена как решенная")

def delete_single_escalation(escalation_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM support_messages WHERE escalation_id = ?', (escalation_id,))
    cursor.execute('DELETE FROM escalations WHERE id = ?', (escalation_id,))
    conn.commit()
    conn.close()
    logger.info(f"Эскалация #{escalation_id} и все связанные сообщения были удалены.")

def add_support_message(escalation_id, sender_role, message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO support_messages (escalation_id, sender_role, message)
        VALUES (?, ?, ?)
    ''', (escalation_id, sender_role, message))
    conn.commit()
    conn.close()
    logger.info(f"Новое сообщение в поддержку (Эскалация #{escalation_id}, Отправитель: {sender_role})")

def get_support_messages(escalation_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM support_messages WHERE escalation_id = ? ORDER BY created_at ASC', (escalation_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_student_escalations(student_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM escalations WHERE student_username = ? ORDER BY created_at DESC', (student_username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_unread_admin_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM escalations WHERE status = "active" AND is_read_by_admin = 0')
    esc_count = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*) FROM support_messages sm
        JOIN escalations e ON sm.escalation_id = e.id
        WHERE e.status = "active" AND sm.sender_role = "Студент" AND sm.is_read = 0
    ''')
    msg_count = cursor.fetchone()[0]
    conn.close()
    return esc_count + msg_count

def get_unread_student_count(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM support_messages sm
        JOIN escalations e ON sm.escalation_id = e.id
        WHERE e.status = "active" AND e.student_username = ? AND sm.sender_role = "Администратор" AND sm.is_read = 0
    ''', (username,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def mark_admin_read():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE escalations SET is_read_by_admin = 1 WHERE is_read_by_admin = 0')
    cursor.execute('UPDATE support_messages SET is_read = 1 WHERE sender_role = "Студент" AND is_read = 0')
    conn.commit()
    conn.close()

def mark_student_read(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE support_messages SET is_read = 1 
        WHERE sender_role = "Администратор" AND is_read = 0 AND escalation_id IN (
            SELECT id FROM escalations WHERE student_username = ?
        )
    ''', (username,))
    conn.commit()
    conn.close()

def save_chat_message(student_username, role, content, context_docs=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    context_json = None
    if context_docs:
        # Save minimal context info
        context_list = [{"module": doc.metadata.get('module', 'N/A'), "topic": doc.metadata.get('topic', 'N/A')} for doc in context_docs]
        context_json = json.dumps(context_list, ensure_ascii=False)
        
    cursor.execute('''
        INSERT INTO chat_messages (student_username, role, content, context_json)
        VALUES (?, ?, ?, ?)
    ''', (student_username, role, content, context_json))
    conn.commit()
    conn.close()

def get_chat_history(student_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM chat_messages WHERE student_username = ? ORDER BY created_at ASC', (student_username,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        context = None
        if row['context_json']:
            try:
                context_data = json.loads(row['context_json'])
                # We mock Document objects for the UI to display
                class MockDoc:
                    def __init__(self, metadata):
                        self.metadata = metadata
                context = [MockDoc(c) for c in context_data]
            except:
                pass
        history.append({
            "role": row['role'],
            "content": row['content'],
            "context": context
        })
    return history

def clear_chat_history(student_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_messages WHERE student_username = ?', (student_username,))
    conn.commit()
    conn.close()

def delete_student_escalations(student_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM support_messages 
        WHERE escalation_id IN (SELECT id FROM escalations WHERE student_username = ?)
    ''', (student_username,))
    cursor.execute('DELETE FROM escalations WHERE student_username = ?', (student_username,))
    conn.commit()
    conn.close()
    logger.info(f"Все обращения в поддержку для студента {student_username} были удалены.")
