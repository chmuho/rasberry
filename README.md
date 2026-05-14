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

## 프로젝트 구조

```text
.
├── app.py                    # Flask 관리자 웹 서버
├── final_doorlock.py          # 라즈베리파이 도어락 메인 실행 코드
├── database.py                # SQLite 초기화 및 로그/사용자 저장
├── anti_spoofing.py           # Anti-spoofing 모델 연동
├── mask_detector.py           # 마스크 착용 여부 및 상안부 영역 계산
├── templates/
│   ├── login.html             # 관리자 로그인 화면
│   └── logs.html              # 출입 로그/제어 대시보드
├── static/
│   ├── app.js
│   ├── styles.css
│   ├── manifest.json
│   └── service-worker.js
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
DOORLOCK_ADMIN_PW=change-me
DOORLOCK_SECRET_KEY=change-this-secret-key
RASPBERRY_PI_IP=127.0.0.1
RASPBERRY_PI_PORT=5001
ANTI_SPOOF_DIR=./Silent-Face-Anti-Spoofing
```

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
