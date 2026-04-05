"""Launcher used when packaging the Streamlit app as a Windows executable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from streamlit.web import cli as stcli


def get_runtime_base_dir() -> Path:
    """Return the directory that contains bundled app resources."""

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def main() -> None:
    """Start the bundled Streamlit app from the extracted resource directory."""

    app_path = get_runtime_base_dir() / "app.py"
    if not app_path.exists():
        raise FileNotFoundError(f"app.py was not bundled: {app_path}")

    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=localhost",
        "--server.headless=false",
        "--browser.serverAddress=localhost",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
