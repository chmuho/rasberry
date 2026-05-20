import face_recognition
import cv2
from picamera2 import Picamera2
import numpy as np
import os
from gpiozero import Servo, LED, Button
from time import sleep, time as get_time
import sys
from flask import Flask, request, jsonify
import threading
from database import save_log
from anti_spoofing import check_real_face
from mask_detector import detect_mask_by_landmark, get_upper_face_location

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOOR_OPEN_SECONDS = 10
 
# --- 웹 원격 제어 서버 ---
rpi_server = Flask(__name__)

def capture_frame_after_countdown(message):
    print(message)
    picam2.start()
    warmup_start = get_time()
    while get_time() - warmup_start < 3.0:
        if int(get_time() * 4) % 2 == 0:
            led_green.on()
        else:
            led_green.off()
    led_green.off()
    frame = picam2.capture_array()
    picam2.stop()
    return frame
 
@rpi_server.route('/api/control/door', methods=['POST'])
def remote_door_control():
    try:
        data = request.get_json()
        action = data.get("action")
        if action == "open":
            print("\n🌐 [웹 원격 제어] 문 열기 요청 수신")
            led_red.off(); led_green.on(); servo.min()
            save_log("원격제어", "REMOTE_OPEN", "")
            return jsonify({"success": True, "message": "Door opened"}), 200
        elif action == "close":
            print("\n🌐 [웹 원격 제어] 문 닫기 요청 수신")
            servo.max(); sleep(0.5); servo.detach()
            led_green.off(); led_red.on()
            save_log("원격제어", "REMOTE_CLOSE", "")
            return jsonify({"success": True, "message": "Door closed"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": "Invalid action"}), 400
 
@rpi_server.route('/api/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({"success": False, "error": "이름을 입력해주세요"}), 400
 
        frame = capture_frame_after_countdown(f"\n📸 [{name}] 등록 시작... 3초 후 촬영")
 
        locs = face_recognition.face_locations(frame)
        if not locs:
            return jsonify({"success": False, "error": "얼굴을 감지하지 못했습니다"}), 400
 
        cv2.imwrite(os.path.join(BASE_DIR, f"master_{name}.jpg"), frame)
 
        enc_list = face_recognition.face_encodings(frame, locs)
        if enc_list:
            if name not in masters:
                masters[name] = {}
            masters[name]['no_mask'] = enc_list[0]
            print(f"✅ [{name}] 등록 완료!")
            return jsonify({"success": True, "message": f"{name} 등록 완료"}), 200
        else:
            return jsonify({"success": False, "error": "인코딩 실패"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@rpi_server.route('/api/register_mask', methods=['POST'])
def register_mask():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({"success": False, "error": "이름을 입력해주세요"}), 400

        frame = capture_frame_after_countdown(f"\n📸 [{name}] 마스크 등록 시작... 3초 후 촬영")

        mask_path = os.path.join(BASE_DIR, f"master_{name}_mask.jpg")
        cv2.imwrite(mask_path, frame)

        locs = face_recognition.face_locations(frame)
        used_fallback = False

        if locs:
            face_loc = locs[0]
            _, upper_pts = detect_mask_by_landmark(frame, face_loc)
            enc_loc = get_upper_face_location(upper_pts, frame.shape) if upper_pts else face_loc
            enc_loc = enc_loc if enc_loc else face_loc
        else:
            enc_loc = get_center_face_location(frame)
            used_fallback = True

        enc_list = face_recognition.face_encodings(frame, [enc_loc])
        if not enc_list:
            return jsonify({
                "success": False,
                "error": "마스크 사진은 저장했지만 얼굴 인코딩에 실패했습니다. 얼굴을 카메라 중앙에 맞춰 다시 촬영해주세요"
            }), 400

        if name not in masters:
            masters[name] = {}
        masters[name]['mask'] = enc_list[0]
        print(f"✅ [{name}] 마스크 등록 완료!")
        message = f"{name} 마스크 등록 완료"
        if used_fallback:
            message += " (자동 얼굴 감지 실패로 중앙 영역을 사용했습니다)"
        return jsonify({"success": True, "message": message}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
@rpi_server.route('/api/delete_user', methods=['POST'])
def delete_user():
    try:
        data = request.get_json()
        name = data.get('name')
        deleted = []
        for file in os.listdir(BASE_DIR):
            if file.startswith(f'master_{name}') and file.endswith(('.jpg', '.png', '.jpeg')):
                os.remove(os.path.join(BASE_DIR, file))
                deleted.append(file)
        if name in masters:
            del masters[name]
        print(f"🗑 [{name}] 삭제 완료: {deleted}")
        return jsonify({"success": True, "message": f"{name} 삭제 완료"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
def run_rpi_server():
    rpi_server.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
 
# --- 하드웨어 설정 ---
servo = Servo(18, initial_value=1, min_pulse_width=0.0005, max_pulse_width=0.0025)
led_green = LED(17)
led_red = LED(27)
button = Button(22)
 
# --- 카메라 초기화 ---
print("📸 카메라를 초기화합니다...")
try:
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
    picam2.set_controls({"AwbEnable": True, "AeEnable": True})
except Exception as e:
    print(f"❌ 카메라 초기화 실패: {e}")
    sys.exit(1)

def get_center_face_location(frame):
    height, width = frame.shape[:2]
    return (
        int(height * 0.08),
        int(width * 0.85),
        int(height * 0.82),
        int(width * 0.15),
    )
 
def load_master_faces():
    known_encodings = {}
    print("📂 마스터 데이터를 불러오는 중...")
    for file in os.listdir(BASE_DIR):
        if not (file.startswith('master') and file.endswith(('.jpg', '.png', '.jpeg'))):
            continue
        try:
            image_path = os.path.join(BASE_DIR, file)
            image = face_recognition.load_image_file(image_path)
            raw_name = file.replace('master_', '').split('.')[0]
            if '_mask' in raw_name:
                name = raw_name.replace('_mask', ''); key = 'mask'
            else:
                name = raw_name; key = 'no_mask'
            face_locs = face_recognition.face_locations(image)
            enc_loc = face_locs[0] if face_locs else get_center_face_location(image)
            if key == 'mask' and face_locs:
                _, upper_pts = detect_mask_by_landmark(image, enc_loc)
                upper_loc = get_upper_face_location(upper_pts, image.shape) if upper_pts else None
                enc_loc = upper_loc if upper_loc else enc_loc
            enc_list = face_recognition.face_encodings(image, [enc_loc])
            if not enc_list: continue
            enc = enc_list[0]
            if name not in known_encodings: known_encodings[name] = {}
            known_encodings[name][key] = enc
            print(f"✅ 로드 성공: {name} [{key}]")
        except Exception as e:
            print(f"⚠️ {file} 로드 오류: {e}")
    return known_encodings
 
def recognize_face(frame, face_location, known_encodings):
    THRESHOLD_NORMAL = 0.50
    THRESHOLD_MASK = 0.62
    is_masked, upper_pts = detect_mask_by_landmark(frame, face_location)
    unknown_encodings = []

    full_encs = face_recognition.face_encodings(frame, [face_location])
    if full_encs:
        unknown_encodings.append((full_encs[0], 'no_mask', THRESHOLD_NORMAL))

    if upper_pts:
        upper_loc = get_upper_face_location(upper_pts, frame.shape)
        if upper_loc:
            upper_encs = face_recognition.face_encodings(frame, [upper_loc])
            if upper_encs:
                unknown_encodings.append((upper_encs[0], 'mask', THRESHOLD_MASK))

    if not unknown_encodings:
        return None, 1.0, is_masked

    best_name, best_dist, best_key = None, 1.0, None
    for unknown_enc, preferred_key, threshold in unknown_encodings:
        for name, enc_dict in known_encodings.items():
            candidate = enc_dict.get(preferred_key)
            if candidate is None:
                continue
            dist = float(face_recognition.face_distance([candidate], unknown_enc)[0])
            if dist < threshold and dist < best_dist:
                best_dist = dist
                best_name = name
                best_key = preferred_key
    matched_as_masked = best_key == 'mask' if best_key else is_masked
    return best_name, best_dist, matched_as_masked
 
def start_recognition(known_encodings):
    if not known_encodings:
        print("⚠️ 등록된 마스터 얼굴 데이터가 없습니다.")
        return False, "데이터 없음", ""
 
    print("📸 카메라 예열 중... (3초)")
    picam2.start()
    warmup_start = get_time()
    while get_time() - warmup_start < 3.0:
        picam2.capture_array()
        if int(get_time() * 4) % 2 == 0: led_green.on()
        else: led_green.off()
    led_green.off()
    print("🔍 본인 확인 시작...")
 
    start_time = get_time()
    authenticated, found_user, captured_image_path, last_frame = False, "침입자", "", None
    consecutive_count, CONSECUTIVE_NEEDED, last_recognized = 0, 3, None
 
    try:
        frame_count = 0
        while get_time() - start_time < 10:
            if int(get_time() * 2) % 2 == 0: led_green.on()
            else: led_green.off()
 
            frame = picam2.capture_array()
            last_frame = frame
            frame_count += 1
            if frame_count % 3 != 0: continue
 
            face_locations = face_recognition.face_locations(frame)
            used_fallback_location = False
            if not face_locations:
                if frame_count % 9 == 0:
                    print("⚠️ 얼굴을 감지하지 못했습니다. 중앙 영역으로 인식을 시도합니다.")
                face_locations = [get_center_face_location(frame)]
                used_fallback_location = True
            for face_loc in face_locations:
                # Anti-spoofing 9프레임에 1번 체크
                if frame_count % 9 == 0 and not used_fallback_location:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    is_real, spoof_score = check_real_face(frame_bgr, face_loc)
                    if not is_real:
                        print(f"🚫 가짜 얼굴 감지! (score: {spoof_score})")
                        consecutive_count = 0
                        last_recognized = None
                        continue
 
                name, dist, is_masked = recognize_face(frame, face_loc, known_encodings)
                print(f"🔎 인식 결과: name={name}, dist={dist:.3f}, masked={is_masked}")
                if name:
                    if name == last_recognized: consecutive_count += 1
                    else: consecutive_count = 1; last_recognized = name
                    if consecutive_count >= CONSECUTIVE_NEEDED:
                        from database import get_users
                        user_map = get_users()
                        found_user = user_map.get(name, name)
                        authenticated = True; break
                else:
                    consecutive_count = 0; last_recognized = None
 
            if authenticated: break
 
        led_green.off()
 
        if last_frame is not None:
            save_dir = 'static/captures'
            os.makedirs(save_dir, exist_ok=True)
            if not authenticated:
                captured_image_path = f"{save_dir}/stranger_{int(get_time())}.jpg"
                cv2.imwrite(captured_image_path, last_frame)
                print(f"📸 침입자 사진 저장: {captured_image_path}")
 
    finally:
        picam2.stop()
        led_green.off()
 
    return authenticated, found_user, captured_image_path
 
# --- 메인 실행 루프 ---
if __name__ == "__main__":
    masters = load_master_faces()
    web_thread = threading.Thread(target=run_rpi_server)
    web_thread.daemon = True
    web_thread.start()
 
    led_red.on(); led_green.off(); servo.max()
    sleep(0.5); servo.detach()
    print("🔒 시스템 대기 중...")
 
    try:
        while True:
            if button.is_pressed:
                print("\n🔘 버튼 클릭됨! 본인 확인 시작...")
                led_red.off()
                is_ok, user_name, img_path = start_recognition(masters)
                if is_ok:
                    print(f"🔓 환영합니다, {user_name}님!")
                    save_log(user_name, "ACCESS", img_path)
                    led_green.on(); servo.min(); sleep(DOOR_OPEN_SECONDS); servo.max()
                    sleep(0.5); servo.detach(); led_green.off()
                else:
                    print("❌ 접근 거부")
                    save_log("침입자", "INTRUSION", img_path)
                    for _ in range(3): led_red.on(); sleep(0.2); led_red.off(); sleep(0.2)
                led_red.on()
                print("🔒 시스템 대기 중...")
            sleep(0.1)
    except KeyboardInterrupt:
        print("\n👋 프로그램을 종료합니다.")
    finally:
        servo.detach(); led_red.off(); led_green.off()
