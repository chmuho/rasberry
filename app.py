from flask import Flask, jsonify, render_template, request, send_from_directory, session, redirect
import sqlite3
from database import init_db, save_log, add_user, get_users
import requests
import os
from functools import wraps

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.secret_key = os.getenv('DOORLOCK_SECRET_KEY', 'change-this-secret-key')
init_db()

RASPBERRY_PI_IP = os.getenv('RASPBERRY_PI_IP', '127.0.0.1')
RASPBERRY_PI_PORT = os.getenv('RASPBERRY_PI_PORT', '5001')
RASPBERRY_PI_BASE_URL = f"http://{RASPBERRY_PI_IP}:{RASPBERRY_PI_PORT}"
CAPTURE_DIR = os.path.join(app.root_path, 'static', 'captures')

ADMIN_ID = os.getenv('DOORLOCK_ADMIN_ID', 'admin')
ADMIN_PW = os.getenv('DOORLOCK_ADMIN_PW', 'change-me')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path.startswith('/api/') or request.path == '/logs':
                return jsonify({"error": "unauthorized"}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if username == ADMIN_ID and password == ADMIN_PW:
        session['logged_in'] = True
        return jsonify({"success": True}), 200
    return jsonify({"success": False, "error": "아이디 또는 비밀번호가 틀렸습니다"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/static/captures/<path:filename>')
def custom_static(filename):
    return send_from_directory(CAPTURE_DIR, filename)

def get_logs():
    conn = sqlite3.connect("doorlock_logs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, user_name, status, image_path FROM access_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"name": row[1] or "침입자", "time": row[0], "status": row[2], "image": row[3]} for row in rows]

@app.route("/master/<filename>")
@login_required
def master_photo(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route("/")
@login_required
def home():
    return render_template("logs.html", logs=get_logs())

@app.route("/logs")
@login_required
def logs():
    return jsonify(get_logs())

@app.route("/api/intrusion_count")
@login_required
def api_intrusion_count():
    try:
        conn = sqlite3.connect("doorlock_logs.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM access_logs WHERE status IN ('INTRUSION', 'INTRUSION_ALERT')")
        result = cursor.fetchone()
        conn.close()
        return jsonify({"success": True, "intrusion_count": result[0] if result else 0}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/users")
@login_required
def api_users():
    try:
        user_map = get_users()
        users = {}
        master_dir = BASE_DIR
        for file in os.listdir(master_dir):
            if file.startswith('master') and file.endswith(('.jpg', '.png', '.jpeg')):
                raw = file.replace('master_', '').split('.')[0]
                name = raw.split('_mask')[0] if '_mask' in raw else raw.rstrip('0123456789').rstrip('_')
                if name not in users:
                    users[name] = {'id': name, 'name': user_map.get(name, name), 'photos': []}
                users[name]['photos'].append(file)
        return jsonify(list(users.values())), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/delete_user", methods=["POST"])
@login_required
def api_delete_user():
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        rpi_response = requests.post(f"{RASPBERRY_PI_BASE_URL}/api/delete_user", json={"name": user_id}, timeout=5)
        if rpi_response.status_code == 200:
            conn = sqlite3.connect("doorlock_logs.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": "라즈베리파이 응답 오류"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/door_control", methods=["POST"])
@login_required
def api_door_control():
    try:
        data = request.get_json() or {}
        action = data.get("action")
        if action not in ("open", "close"):
            return jsonify({"success": False, "error": "action 오류"}), 400
        rpi_response = requests.post(f"{RASPBERRY_PI_BASE_URL}/api/control/door", json={"action": action}, timeout=5)
        if rpi_response.status_code == 200:
            return jsonify({"success": True, "message": f"문 {action} 완료"}), 200
        return jsonify({"success": False, "error": "라즈베리파이 응답 오류"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
@login_required
def api_register():
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', '').strip()
        display_name = data.get('display_name', '').strip()
        if not user_id or not display_name:
            return jsonify({"success": False, "error": "ID와 이름을 입력해주세요"}), 400
        rpi_response = requests.post(f"{RASPBERRY_PI_BASE_URL}/api/register", json={"name": user_id}, timeout=15)
        if rpi_response.status_code == 200:
            add_user(user_id, display_name)
            return jsonify({"success": True, "message": f"{display_name} 등록 완료"}), 200
        return jsonify({"success": False, "error": "라즈베리파이 응답 오류"}), 500
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "error": "응답 시간 초과"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system_status")
def api_system_status():
    try:
        conn = sqlite3.connect("doorlock_logs.db")
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp FROM access_logs ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return jsonify({"status": "online", "last_activity": result[0] if result else None, "camera": "active"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
