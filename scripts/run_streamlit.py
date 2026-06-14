from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_LOG = ROOT / "streamlit.out.log"
ERR_LOG = ROOT / "streamlit.err.log"


def main() -> None:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ]
    with OUT_LOG.open("w", encoding="utf-8") as stdout, ERR_LOG.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    print(process.pid)


if __name__ == "__main__":
    main()
