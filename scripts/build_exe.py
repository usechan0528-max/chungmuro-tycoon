from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _add_data(source: str, target: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{target}"


def main() -> int:
    if sys.platform != "win32":
        print(
            "ChungmuroTycoon의 공식 패키징 대상은 Windows입니다. "
            "Windows .exe는 Windows + Python 3.11/3.12 환경에서 이 스크립트를 실행하세요."
        )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "main.py",
        "--name",
        "ChungmuroTycoon",
        "--add-data",
        _add_data("data/seed", "data/seed"),
        "--add-data",
        _add_data("assets", "assets"),
    ]
    if (ROOT_DIR / "data" / "game.db").exists():
        command.extend(["--add-data", _add_data("data/game.db", "data")])
    return subprocess.call(command, cwd=ROOT_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
