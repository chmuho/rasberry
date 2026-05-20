# Edge AI Smart Doorlock

라즈베리파이와 카메라를 이용해 얼굴을 인식하고, 출입 결과를 웹 대시보드에서 확인할 수 있는 스마트 도어락 프로젝트입니다. 얼굴 인식, 마스크 착용 상태 대응, anti-spoofing, 출입 로그 저장, 웹 기반 원격 제어 기능을 하나의 흐름으로 연결하는 것을 목표로 했습니다.

## 주요 기능

- 라즈베리파이 카메라 기반 얼굴 인식
- 등록 사용자와 침입자 구분
- 마스크 착용 상황을 고려한 얼굴 영역 인식
- Silent Face Anti-Spoofing 기반 실제 얼굴 판별
- 서보 모터, LED, 버튼을 이용한 도어락 제어
- SQLite 출입 로그 저장
- Flask 기반 관리자 웹 대시보드
- 사용자 등록/삭제 API
- 웹에서 도어락 열기/닫기 원격 제어
- 침입 감지 시 카카오톡 나에게 보내기 알림

## 프로젝트 구조

```text
.
├── app.py                    # Flask 관리자 웹 서버
├── final_doorlock.py          # 라즈베리파이 도어락 메인 실행 코드
├── database.py                # SQLite 초기화 및 로그/사용자 저장
├── anti_spoofing.py           # Anti-spoofing 모델 연동
├── mask_detector.py           # 마스크 착용 여부 및 상안부 영역 계산
├── kakao_token_helper.py       # 카카오톡 알림용 토큰 발급 도우미
├── templates/
│   ├── login.html             # 관리자 로그인 화면
│   ├── logs.html              # 출입 로그/제어 대시보드
│   ├── find_id.html           # 관리자 아이디 찾기 화면
│   ├── forgot_password.html   # 관리자 비밀번호 찾기 화면
│   ├── reset_password.html    # 관리자 비밀번호 재설정 화면
│   ├── change_id.html         # 관리자 아이디 변경 화면
│   └── change_password.html   # 관리자 비밀번호 변경 화면
├── static/
│   ├── lock.jpg
│   └── manifest.json
└── Silent-Face-Anti-Spoofing/ # Anti-spoofing 외부 모델 코드
```

## 실행 환경

- Raspberry Pi
- Python 3
- PiCamera2 지원 카메라
- Servo motor
- LED
- Button
- SQLite
- Flask

필요한 주요 Python 패키지:

```bash
pip install flask requests opencv-python numpy face-recognition picamera2 gpiozero
```

`face-recognition`, `picamera2`, `gpiozero`는 실행 환경에 따라 OS 패키지나 라즈베리파이 설정이 먼저 필요할 수 있습니다.

Anti-spoofing 기능은 외부 오픈소스 프로젝트인 Silent-Face-Anti-Spoofing 코드를 사용합니다. 저장소 용량과 외부 코드 관리를 위해 이 폴더는 Git에 포함하지 않았으므로, 실행 전에 프로젝트 루트에서 별도로 내려받습니다.

```bash
git clone https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git
```

기본 경로가 아닌 곳에 설치했다면 `ANTI_SPOOF_DIR` 환경변수에 해당 경로를 지정합니다.

## 환경 변수

공개 저장소에 관리자 계정, 비밀번호, secret key를 직접 올리지 않기 위해 환경변수로 분리했습니다. `.env.example`을 참고해 로컬 환경에 맞게 설정합니다.

```bash
DOORLOCK_ADMIN_ID=admin
DOORLOCK_ADMIN_PW=admin1234
DOORLOCK_RECOVERY_CODE=doorlock-reset
DOORLOCK_SECRET_KEY=change-this-secret-key
RASPBERRY_PI_IP=127.0.0.1
RASPBERRY_PI_PORT=5001
DOORLOCK_WEB_URL=http://127.0.0.1:5000
ANTI_SPOOF_DIR=./Silent-Face-Anti-Spoofing
KAKAO_ALERT_ENABLED=false
KAKAO_REST_API_KEY=
KAKAO_CLIENT_SECRET=
KAKAO_REDIRECT_URI=http://localhost:8080/callback
KAKAO_ACCESS_TOKEN=
KAKAO_REFRESH_TOKEN=
```

## 카카오톡 침입 알림 설정

침입자가 감지되면 카카오톡 나와의 채팅방으로 알림을 보낼 수 있습니다. 토큰과 API 키는 개인정보에 해당하므로 `.env`에만 저장하고 GitHub에는 올리지 않습니다.

1. Kakao Developers에서 애플리케이션을 생성합니다.
2. 플랫폼 또는 카카오 로그인 설정에서 Redirect URI에 `http://localhost:8080/callback`을 등록합니다.
3. 동의항목에서 카카오톡 메시지 전송 권한을 설정합니다.
4. REST API 키를 `.env`의 `KAKAO_REST_API_KEY`에 입력합니다. Client secret을 사용 중이면 `KAKAO_CLIENT_SECRET`에도 값을 입력합니다.
5. 아래 명령으로 인증 주소를 출력합니다.

```bash
python kakao_token_helper.py auth-url
```

6. 출력된 주소로 접속해 카카오 로그인을 완료한 뒤, 이동된 주소의 `code=` 뒤 값을 복사합니다.
7. 복사한 code 값으로 토큰을 발급합니다.

```bash
python kakao_token_helper.py token 복사한_code값
```

8. 출력된 `KAKAO_ACCESS_TOKEN`, `KAKAO_REFRESH_TOKEN`을 `.env`에 넣고 `KAKAO_ALERT_ENABLED=true`로 변경합니다.

카카오 access token은 만료될 수 있습니다. 프로그램은 refresh token으로 access token 갱신을 시도하며, 새 refresh token이 출력되면 `.env` 값을 갱신해야 합니다.

## 실행 방법

Flask 관리자 웹 서버:

```bash
python app.py
```

브라우저에서 접속:

```text
http://127.0.0.1:5000
```

라즈베리파이 도어락 메인 코드:

```bash
python final_doorlock.py
```

웹 서버는 기본적으로 라즈베리파이 제어 서버를 `RASPBERRY_PI_IP:RASPBERRY_PI_PORT` 주소로 호출합니다. 실제 기기에서 사용할 때는 라즈베리파이의 IP 주소에 맞게 환경변수를 설정해야 합니다.

## 데이터 저장

출입 기록은 SQLite DB에 저장됩니다.

- `access_logs`: 출입 시간, 사용자 이름, 상태, 촬영 이미지 경로
- `users`: 등록 사용자 ID와 표시 이름

주요 상태값:

- `ACCESS`: 등록 사용자 출입 성공
- `INTRUSION`: 미등록 사용자 또는 인증 실패
- `REMOTE_OPEN`: 웹 원격 열기
- `REMOTE_CLOSE`: 웹 원격 닫기

## 공개 저장소 주의사항

다음 파일은 개인정보 또는 로컬 실행 데이터가 포함될 수 있어 Git에 올리지 않도록 `.gitignore`에 추가했습니다.

- `.env`, `.env.*`
- `*.db`
- `__pycache__/`, `*.pyc`
- `master_*.jpg`, `master_*.png`
- `static/captures/`
- 모델 가중치 파일(`*.onnx`, `*.pth`, `*.pt` 등)

이미 Git에 추적되고 있던 DB나 캐시 파일은 `.gitignore`만으로 자동 제외되지 않으므로, 커밋 전에 Source Control에서 제외되었는지 확인해야 합니다.

## 향후 개선 방향

- 관리자 계정 관리 기능 추가
- 실시간 카메라 스트리밍
- 침입 감지 시 모바일 푸시 또는 메신저 알림
- 사용자 등록 UX 개선
- 하드웨어 예외 처리 및 로그 강화
- 배포 환경용 설정 파일 분리
