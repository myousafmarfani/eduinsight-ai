"""Start the backend and the frontend together:  python run.py

Options: --backend-only, --frontend-only, --no-reload. Works on Windows, macOS and Linux.
(Equivalent to running `uvicorn app.main:app --reload` and `streamlit run frontend/streamlit_app.py`.)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    commands: list[list[str]] = []
    if not args.frontend_only:
        cmd = [sys.executable, "-m", "uvicorn", "app.main:app"]
        if not args.no_reload:
            cmd.append("--reload")
        commands.append(cmd)
    if not args.backend_only:
        commands.append([sys.executable, "-m", "streamlit", "run", "frontend/streamlit_app.py"])

    processes = [subprocess.Popen(cmd, cwd=ROOT) for cmd in commands]
    print("Backend: http://127.0.0.1:8000/docs | Frontend: http://localhost:8501 | Ctrl+C to stop")
    try:
        while all(p.poll() is None for p in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
