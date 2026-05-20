from flask import Flask, jsonify, render_template, request, send_from_directory, session, redirect, Response, stream_with_context
import sqlite3
from database import (
    init_db, save_log, add_user, get_users,
    get_admin_id, set_admin_id, set_admin_password, verify_admin_password
)
import requests
import os
from functools import wraps

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_local_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_local_env()

app.secret_key = os.getenv('DOORLOCK_SECRET_KEY', 'change-this-secret-key')
init_db()

RASPBERRY_PI_IP = os.getenv('RASPBERRY_PI_IP', '127.0.0.1')
RASPBERRY_PI_PORT = os.getenv('RASPBERRY_PI_PORT', '5001')
RASPBERRY_PI_BASE_URL = f"http://{RASPBERRY_PI_IP}:{RASPBERRY_PI_PORT}"
CAPTURE_DIR = os.path.join(app.root_path, 'static', 'captures')

ADMIN_ID = os.getenv('DOORLOCK_ADMIN_ID', 'admin')
ADMIN_PW = os.getenv('DOORLOCK_ADMIN_PW', 'admin1234')
RECOVERY_CODE = os.getenv('DOORLOCK_RECOVERY_CODE', 'doorlock-reset')

def current_admin_id():
    return get_admin_id(ADMIN_ID)

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

@app.route('/forgot-password')
def forgot_password_page():
    return render_template('forgot_password.html')

@app.route('/reset-password')
def reset_password_page():
    if not session.get('password_reset_allowed'):
        return redirect('/forgot-password')
    return render_template('reset_password.html')

@app.route('/find-id')
def find_id_page():
    return render_template('find_id.html')

@app.route('/change-password')
@login_required
def change_password_page():
    return render_template('change_password.html')

@app.route('/change-id')
@login_required
def change_id_page():
    return render_template('change_id.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if username == current_admin_id() and verify_admin_password(password, ADMIN_PW):
        session['logged_in'] = True
        return jsonify({"success": True}), 200
    return jsonify({"success": False, "error": "아이디 또는 비밀번호가 틀렸습니다"}), 401

@app.route('/api/id/find', methods=['POST'])
def api_find_id():
    data = request.get_json() or {}
    recovery_code = (data.get('recovery_code') or '').strip()
    if recovery_code != RECOVERY_CODE:
        return jsonify({"success": False, "error": "복구 코드가 올바르지 않습니다"}), 400
    return jsonify({"success": True, "admin_id": current_admin_id()}), 200

@app.route('/api/id/change', methods=['POST'])
@login_required
def api_change_id():
    data = request.get_json() or {}
    current_password = (data.get('current_password') or '').strip()
    new_admin_id = (data.get('new_admin_id') or '').strip()

    if not verify_admin_password(current_password, ADMIN_PW):
        return jsonify({"success": False, "error": "현재 비밀번호가 올바르지 않습니다"}), 400
    if len(new_admin_id) < 3:
        return jsonify({"success": False, "error": "새 아이디는 3자 이상이어야 합니다"}), 400
    if new_admin_id == current_admin_id():
        return jsonify({"success": False, "error": "현재 아이디와 다른 아이디를 입력해주세요"}), 400
    if not set_admin_id(new_admin_id):
        return jsonify({"success": False, "error": "아이디를 저장하지 못했습니다"}), 500

    session.clear()
    return jsonify({"success": True, "message": "아이디가 변경되었습니다. 다시 로그인해주세요"}), 200

@app.route('/api/password/find', methods=['POST'])
def api_find_password():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    recovery_code = (data.get('recovery_code') or '').strip()

    if username != current_admin_id():
        return jsonify({"success": False, "error": "관리자 아이디가 올바르지 않습니다"}), 400
    if recovery_code != RECOVERY_CODE:
        return jsonify({"success": False, "error": "복구 코드가 올바르지 않습니다"}), 400

    session['password_reset_allowed'] = True
    session['password_reset_username'] = username
    return jsonify({"success": True, "message": "본인 확인이 완료되었습니다"}), 200

@app.route('/api/password/reset', methods=['POST'])
def api_reset_password():
    if not session.get('password_reset_allowed'):
        return jsonify({"success": False, "error": "비밀번호 찾기에서 본인 확인을 먼저 완료해주세요"}), 403

    data = request.get_json() or {}
    new_password = (data.get('new_password') or '').strip()
    confirm_password = (data.get('confirm_password') or '').strip()

    if len(new_password) < 8:
        return jsonify({"success": False, "error": "새 비밀번호는 8자 이상이어야 합니다"}), 400
    if new_password != confirm_password:
        return jsonify({"success": False, "error": "새 비밀번호 확인이 일치하지 않습니다"}), 400
    if not set_admin_password(new_password):
        return jsonify({"success": False, "error": "비밀번호를 저장하지 못했습니다"}), 500

    session.clear()
    return jsonify({"success": True, "message": "비밀번호가 재설정되었습니다"}), 200

@app.route('/api/password/change', methods=['POST'])
@login_required
def api_change_password():
    data = request.get_json() or {}
    current_password = (data.get('current_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()
    confirm_password = (data.get('confirm_password') or '').strip()

    if not verify_admin_password(current_password, ADMIN_PW):
        return jsonify({"success": False, "error": "현재 비밀번호가 올바르지 않습니다"}), 400
    if len(new_password) < 8:
        return jsonify({"success": False, "error": "새 비밀번호는 8자 이상이어야 합니다"}), 400
    if new_password != confirm_password:
        return jsonify({"success": False, "error": "새 비밀번호 확인이 일치하지 않습니다"}), 400
    if current_password == new_password:
        return jsonify({"success": False, "error": "현재 비밀번호와 다른 비밀번호를 입력해주세요"}), 400
    if not set_admin_password(new_password):
        return jsonify({"success": False, "error": "비밀번호를 저장하지 못했습니다"}), 500

    session.clear()
    return jsonify({"success": True, "message": "비밀번호가 변경되었습니다. 다시 로그인해주세요"}), 200

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
    cursor.execute("PRAGMA table_info(access_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    if "failure_reason" in columns:
        cursor.execute("SELECT timestamp, user_name, status, image_path, failure_reason FROM access_logs ORDER BY id DESC")
    else:
        cursor.execute("SELECT timestamp, user_name, status, image_path, '' FROM access_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "name": row[1] or "침입자",
        "time": row[0],
        "status": row[2],
        "image": row[3],
        "reason": row[4] or "",
    } for row in rows]

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

@app.route("/api/camera/stream")
@login_required
def api_camera_stream():
    try:
        rpi_response = requests.get(
            f"{RASPBERRY_PI_BASE_URL}/api/camera/stream",
            stream=True,
            timeout=(3, None)
        )
        if rpi_response.status_code != 200:
            return jsonify({"success": False, "error": "카메라를 사용할 수 없습니다"}), rpi_response.status_code

        def proxy_stream():
            try:
                for chunk in rpi_response.iter_content(chunk_size=4096):
                    if chunk:
                        yield chunk
            finally:
                rpi_response.close()

        return Response(
            stream_with_context(proxy_stream()),
            content_type=rpi_response.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        )
    except requests.exceptions.RequestException:
        return jsonify({"success": False, "error": "라즈베리파이 카메라 서버에 연결할 수 없습니다"}), 503

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

@app.route("/api/statistics")
@login_required
def api_statistics():
    try:
        conn = sqlite3.connect("doorlock_logs.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM access_logs
            WHERE status='ACCESS' AND date(timestamp)=date('now', 'localtime')
        """)
        today_access_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM access_logs
            WHERE status IN ('INTRUSION', 'INTRUSION_ALERT')
              AND date(timestamp)=date('now', 'localtime')
        """)
        today_intrusion_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT user_name, timestamp FROM access_logs
            WHERE status='ACCESS'
            ORDER BY id DESC LIMIT 1
        """)
        latest_access = cursor.fetchone()

        cursor.execute("""
            SELECT user_name, COUNT(*) as count FROM access_logs
            WHERE status='ACCESS'
            GROUP BY user_name
            ORDER BY count DESC, user_name ASC
            LIMIT 6
        """)
        user_access_counts = [
            {"name": row[0] or "이름 없음", "count": row[1]}
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count FROM access_logs
            WHERE status IN ('INTRUSION', 'INTRUSION_ALERT')
              AND datetime(timestamp) >= datetime('now', 'localtime', '-24 hours')
            GROUP BY hour
            ORDER BY hour ASC
        """)
        hourly_map = {row[0]: row[1] for row in cursor.fetchall()}
        hourly_intrusions = [
            {"hour": f"{hour:02d}", "count": hourly_map.get(f"{hour:02d}", 0)}
            for hour in range(24)
        ]

        conn.close()
        return jsonify({
            "today_access_count": today_access_count,
            "today_intrusion_count": today_intrusion_count,
            "user_count": user_count,
            "latest_access_user": latest_access[0] if latest_access else None,
            "latest_access_time": latest_access[1] if latest_access else None,
            "user_access_counts": user_access_counts,
            "hourly_intrusions": hourly_intrusions,
        })
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

        conn = sqlite3.connect("doorlock_logs.db")
        cursor = conn.cursor()
        for user_id, user in users.items():
            cursor.execute("""
                SELECT COUNT(*), MAX(timestamp) FROM access_logs
                WHERE status='ACCESS' AND user_name=?
            """, (user['name'],))
            display_count, display_last = cursor.fetchone()
            cursor.execute("""
                SELECT COUNT(*), MAX(timestamp) FROM access_logs
                WHERE status='ACCESS' AND user_name=?
            """, (user_id,))
            id_count, id_last = cursor.fetchone()
            user['access_count'] = (display_count or 0) + (id_count or 0)
            user['last_access_time'] = max(
                [t for t in (display_last, id_last) if t],
                default=None
            )
        conn.close()

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
        try:
            error = rpi_response.json().get("error")
        except ValueError:
            error = None
        return jsonify({"success": False, "error": error or "라즈베리파이 응답 오류"}), 500
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "error": "응답 시간 초과"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/register_mask", methods=["POST"])
@login_required
def api_register_mask():
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', '').strip()
        if not user_id:
            return jsonify({"success": False, "error": "ID를 입력해주세요"}), 400
        rpi_response = requests.post(
            f"{RASPBERRY_PI_BASE_URL}/api/register_mask",
            json={"name": user_id},
            timeout=15
        )
        if rpi_response.status_code == 200:
            message = rpi_response.json().get("message", "마스크 등록 완료")
            return jsonify({"success": True, "message": message}), 200
        try:
            error = rpi_response.json().get("error")
        except ValueError:
            error = None
        return jsonify({"success": False, "error": error or "라즈베리파이 응답 오류"}), 500
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
