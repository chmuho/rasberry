# 라즈베리파이 얼굴인식 코드 (수정 버전)
# 기존 코드에 Flask API 연동 추가

import face_recognition
import cv2
from picamera2 import Picamera2
import numpy as np
import os
import sqlite3
from datetime import datetime
from gpiozero import Servo, LED, Button
from time import sleep, time
import sys
import requests  # 추가: Flask API 호출용

# --- Flask 서버 설정 ---
FLASK_SERVER_URL = "http://[Flask서버IP]:5000"  # 실제 IP로 변경 필요

# --- 1. 하드웨어 설정 ---
servo = Servo(18, initial_value=1, min_pulse_width=0.0005, max_pulse_width=0.0025)
led_green = LED(17)
led_red = LED(27)
button = Button(22)

# --- 2. SQLite DB 초기화 함수 ---
def init_db():
    conn = sqlite3.connect('doorlock_logs.db')
    cursor = conn.cursor()
    # 테이블 생성: 시간, 이름, 결과(성공/실패), 이미지 경로
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_name TEXT,
            status TEXT,
            image_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

# 로그 기록 함수 (Flask API로 전송 추가)
def log_to_db(user_name, status, image_path=""):
    try:
        # 로컬 DB 저장
        conn = sqlite3.connect('doorlock_logs.db')
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO access_logs (timestamp, user_name, status, image_path) VALUES (?, ?, ?, ?)',
                       (now, user_name, status, image_path))
        conn.commit()
        conn.close()

        # Flask API로 전송 (user_name 기반)
        flask_status = "ACCESS" if status == "SUCCESS" else "INTRUSION"

        try:
            response = requests.post(
                f"{FLASK_SERVER_URL}/api/save_log",
                json={
                    "user_name": user_name,
                    "status": flask_status,
                    "image_path": image_path
                },
                timeout=5
            )
            if response.status_code == 200:
                print("✅ Flask API 전송 성공")
            else:
                print(f"⚠️ Flask API 전송 실패: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Flask API 연결 실패: {e}")

    except Exception as e:
        print(f"⚠️ DB 기록 오류: {e}")

# --- 3. 카메라 및 데이터 로드 ---
print("📸 카메라를 초기화합니다...")
try:
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
except Exception as e:
    print(f"❌ 카메라 초기화 실패: {e}")
    sys.exit(1)

def load_master_faces():
    known_encodings = []
    known_names = []
    print("📂 마스터 데이터를 불러오는 중...")
    for file in os.listdir('.'):
        if file.startswith('master') and file.endswith(('.jpg', '.png', '.jpeg')):
            try:
                image = face_recognition.load_image_file(file)
                encoding = face_recognition.face_encodings(image)
                if encoding:
                    known_encodings.append(encoding[0])
                    # 파일명에서 'master_'와 확장자를 제외한 이름을 추출 (예: master_muho.jpg -> muho)
                    name = file.replace('master_', '').split('.')[0]
                    known_names.append(name)
                    print(f"✅ 로드 성공: {name} ({file})")
            except Exception as e:
                print(f"⚠️ {file} 로드 오류: {e}")
    return known_encodings, known_names

# --- 4. 얼굴 인식 루틴 (DB 기록용 정보 반환) ---
def start_recognition(known_encodings, known_names):
    if not known_encodings: return False, "No Data", ""

    print("🔍 카메라 기동... 얼굴을 비춰주세요 (10초 제한)")
    picam2.start()
    start_time = time()
    authenticated = False
    found_user = "Unknown"
    captured_image_path = ""
    last_frame = None

    try:
        while time() - start_time < 10:
            led_green.on()
            sleep(0.05)
            led_green.off()

            frame = picam2.capture_array()
            last_frame = frame  # 최신 프레임 보관
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

            face_locations = face_recognition.face_locations(small_frame)
            face_encodings = face_recognition.face_encodings(small_frame, face_locations)

            for face_encoding in face_encodings:
                distances = face_recognition.face_distance(known_encodings, face_encoding)
                if len(distances) > 0:
                    min_dist = min(distances)
                    if min_dist < 0.4:
                        best_match_index = np.argmin(distances)
                        found_user = known_names[best_match_index]
                        authenticated = True
                        break
            if authenticated: break

        # 인증 실패 시 외부인 사진 저장
        if not authenticated and last_frame is not None:
            if not os.path.exists('captures'):
                os.makedirs('captures')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            captured_image_path = f"captures/stranger_{timestamp}.jpg"
            # RGB를 BGR로 변환하여 OpenCV로 저장
            cv2.imwrite(captured_image_path, cv2.cvtColor(last_frame, cv2.COLOR_RGB2BGR))
            print(f"📸 외부인 사진 저장됨: {captured_image_path}")

    finally:
        picam2.stop()

    return authenticated, found_user, captured_image_path

# --- 5. 메인 실행 루프 ---
init_db()
masters, master_names = load_master_faces()

led_red.on()
led_green.off()
servo.max()

print("------------------------------------------")
print("🔒 시스템 대기 중... 버튼을 누르면 시작합니다.")
print("------------------------------------------")

try:
    while True:
        if button.is_pressed:
            print("\n🔘 버튼 클릭됨! 본인 확인 시작...")
            led_red.off()

            is_ok, user_name, img_path = start_recognition(masters, master_names)

            if is_ok:
                print(f"🔓 [인증 성공] 환영합니다, {user_name}님!")
                log_to_db(user_name, "SUCCESS")
                led_green.on()
                servo.min()
                sleep(5)
                servo.max()
                led_green.off()
                print("🔒 문이 다시 잠겼습니다.")
            else:
                print("❌ [인증 실패] 접근 거부")
                log_to_db("Unknown", "FAILED", img_path)
                for _ in range(3):
                    led_red.on()
                    sleep(0.2)
                    led_red.off()
                    sleep(0.2)

            led_red.on()
            print("\n🔒 시스템 대기 중...")
        sleep(0.1)

except KeyboardInterrupt:
    print("\n👋 프로그램을 종료합니다.")
finally:
    servo.detach()
    led_red.off()
    led_green.off()
    try: picam2.stop()
    except: pass