import json
import os
import sys
from urllib import parse, request
from urllib.error import HTTPError, URLError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REDIRECT_URI = "http://localhost:8080/callback"


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


def post_json(url, data):
    encoded = parse.urlencode(data).encode("utf-8")
    req = request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def print_auth_url(rest_api_key, redirect_uri):
    params = parse.urlencode({
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "talk_message",
    })
    print("아래 주소를 브라우저에 붙여넣고 카카오 로그인/동의를 진행하세요.\n")
    print(f"https://kauth.kakao.com/oauth/authorize?{params}\n")
    print("동의 후 이동된 주소에서 code= 뒤 값을 복사해서 다음 명령에 넣으면 됩니다.")
    print(f"python kakao_token_helper.py token 복사한_code값")


def exchange_token(rest_api_key, redirect_uri, code, client_secret=""):
    data = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if client_secret:
        data["client_secret"] = client_secret
    payload = post_json("https://kauth.kakao.com/oauth/token", data)
    print(".env에 아래 값을 추가하거나 교체하세요.\n")
    print("KAKAO_ALERT_ENABLED=true")
    print(f"KAKAO_ACCESS_TOKEN={payload.get('access_token', '')}")
    print(f"KAKAO_REFRESH_TOKEN={payload.get('refresh_token', '')}")
    print("\n토큰은 개인정보처럼 다루고 GitHub에는 올리지 마세요.")


def main():
    load_local_env()
    rest_api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    client_secret = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()

    if not rest_api_key:
        print(".env에 KAKAO_REST_API_KEY를 먼저 넣어주세요.")
        sys.exit(1)

    command = sys.argv[1] if len(sys.argv) > 1 else "auth-url"
    try:
        if command == "auth-url":
            print_auth_url(rest_api_key, redirect_uri)
        elif command == "token" and len(sys.argv) >= 3:
            exchange_token(rest_api_key, redirect_uri, sys.argv[2].strip(), client_secret)
        else:
            print("사용법:")
            print("python kakao_token_helper.py auth-url")
            print("python kakao_token_helper.py token 복사한_code값")
            sys.exit(1)
    except HTTPError as e:
        print(f"카카오 API 오류: HTTP {e.code}")
        print(e.read().decode("utf-8", errors="ignore"))
        sys.exit(1)
    except (URLError, TimeoutError, ValueError) as e:
        print(f"요청 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
