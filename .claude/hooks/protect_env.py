#!/usr/bin/env python3
"""
PreToolUse 훅 — .env 파일 수정 차단
Edit, Write 도구가 .env 파일을 대상으로 할 경우 차단한다.
"""

import json
import sys
from pathlib import Path


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # 파일 수정 도구만 검사
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")

    # .env 파일만 차단 (.env.example 등은 허용)
    if Path(file_path).name == ".env":
        print(".env 파일은 수정이 허용되지 않습니다. 민감한 정보가 포함되어 있습니다.")
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
