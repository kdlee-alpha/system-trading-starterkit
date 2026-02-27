#!/usr/bin/env python3
"""
Claude Code 훅 → 텔레그램 알림 스크립트

사용법:
  echo '{"message": "..."}' | python3 telegram_notify.py notification
  echo '{"stop_reason": "end_turn"}' | python3 telegram_notify.py stop
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def load_env(env_path: Path) -> dict[str, str]:
    """
    .env 파일에서 환경 변수를 파싱하여 반환한다.
    """
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        # 주석 및 빈 줄 무시
        if not line or line.startswith("#"):
            continue
        # 인라인 주석 제거
        if "#" in line:
            line = line[: line.index("#")].strip()
        if "=" in line:
            key, _, value = line.partition("=")
            # 앞뒤 따옴표 제거
            env_vars[key.strip()] = value.strip().strip("\"'")

    return env_vars


def get_telegram_config() -> tuple[str, str] | None:
    """
    환경 변수 또는 .env 파일에서 텔레그램 설정을 읽어 반환한다.
    설정이 없으면 None을 반환한다.
    """
    # 먼저 실제 환경 변수에서 확인
    bot_token = os.environ.get("TELEGRAM__BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM__CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")

    if bot_token and chat_id:
        return bot_token, chat_id

    # .env 파일에서 읽기 (프로젝트 루트)
    script_dir = Path(__file__).parent.parent.parent  # .claude/hooks/ → 프로젝트 루트
    env_path = script_dir / ".env"
    env_vars = load_env(env_path)

    bot_token = bot_token or env_vars.get("TELEGRAM__BOT_TOKEN", "")
    chat_id = chat_id or env_vars.get("TELEGRAM__CHAT_ID", "")

    if not bot_token or not chat_id:
        return None

    return bot_token, chat_id


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    """
    Telegram Bot API를 통해 메시지를 전송한다.
    urllib.request만 사용하여 외부 의존성 없음.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


def get_project_name() -> str:
    """프로젝트 루트 디렉터리 이름을 반환한다."""
    project_root = Path(__file__).parent.parent.parent
    return project_root.name


def build_message(event_type: str, data: dict) -> str:
    """
    이벤트 타입과 데이터에 따라 텔레그램 메시지를 생성한다.
    """
    project = get_project_name()

    if event_type == "notification":
        return f"🔔 <b>[Claude Code][{project}] 권한 요청</b>"

    if event_type == "stop":
        return f"✅ <b>[Claude Code][{project}] 작업 완료</b>"

    return f"[Claude Code][{project}] 알림: {event_type}"


def main() -> None:
    # CLI 인자로 이벤트 타입 결정
    if len(sys.argv) < 2:
        sys.exit(0)

    event_type = sys.argv[1].lower()

    # stdin에서 JSON 읽기
    try:
        raw = sys.stdin.read()
        data: dict = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    # # jq로 훅 데이터 출력 (디버깅용)
    # if raw.strip():
    #     try:
    #         subprocess.run(["jq", "."], input=raw, text=True, check=False, stdout=sys.stderr)
    #     except FileNotFoundError:
    #         pass  # jq 미설치 시 무시

    # # 훅 데이터를 test.txt에 기록 (디버깅용)
    # if raw.strip():
    #     log_path = Path(__file__).parent.parent.parent / "test.txt"
    #     with log_path.open("a", encoding="utf-8") as f:
    #         f.write(f"[{event_type}]\n{raw}\n\n")

    # 텔레그램 설정 로드
    config = get_telegram_config()
    if config is None:
        # 설정 없으면 조용히 종료
        sys.exit(0)

    bot_token, chat_id = config

    # 메시지 생성 및 전송
    try:
        text = build_message(event_type, data)
        send_telegram_message(bot_token, chat_id, text)
    except Exception:
        # 오류 발생 시 Claude Code 동작에 영향 없도록 조용히 종료
        sys.exit(0)


if __name__ == "__main__":
    main()
