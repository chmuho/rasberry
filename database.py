import sqlite3
from datetime import datetime

DB_PATH = "doorlock_logs.db"

def init_db():
    """DB 초기화"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user_name TEXT,
        status TEXT,
        image_path TEXT
    )
    """)

    # ← 추가
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE,
        display_name TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("DB 생성 완료")

def save_log(user_name, status, image_path):
    """출입 기록 저장 (라즈베리파이 얼굴인식에서 호출)

    Args:
        user_name (str): 사용자 이름 또는 Unknown
        status (str): 'ACCESS' 또는 'INTRUSION'
        image_path (str): 저장된 이미지 경로

    Returns:
        bool: 성공 시 True, 실패 시 False
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
        INSERT INTO access_logs(user_name, timestamp, status, image_path)
        VALUES(?, ?, ?, ?)
        """, (user_name, current_time, status, image_path))

        conn.commit()
        conn.close()

        print(f"[DB 저장] user_name={user_name}, status={status}, time={current_time}")
        return True
        
    except Exception as e:
        print(f"[DB 저장 실패] {e}")
        return False

def add_user(user_id, display_name):
    """사용자 등록"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO users(user_id, display_name)
        VALUES(?, ?)
        """, (user_id, display_name))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[사용자 등록 실패] {e}")
        return False

def get_users():
    """등록된 사용자 목록 반환"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, display_name FROM users")
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}  # {"muho": "무호"}
    except:
        return {}

if __name__ == "__main__":
    init_db()