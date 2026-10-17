"""Native pywebview window setup and its JavaScript API."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from werkzeug.serving import make_server

from .settings import default_media_directory, has_saved_cohn


class DesktopApi:
    """Methods exposed to the main pywebview window."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.connection_window = None
        self.main_window = None

    def choose_download_directory(self, current_directory: str | None = None, parent_window: Any = None) -> str | None:
        dialog_window = parent_window or self.main_window
        if dialog_window is None:
            return None
        import webview

        directory = Path(current_directory).expanduser() if current_directory else default_media_directory()
        if not directory.is_dir():
            directory = directory.parent if directory.parent.is_dir() else Path.home()
        selection = dialog_window.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=str(directory),
        )
        return str(selection[0]) if selection else None

    def choose_config_directory(self, current_directory: str = ".", parent_window: Any = None) -> str | None:
        return self.choose_download_directory(current_directory, parent_window)

    def open_connection_window(self) -> bool:
        import webview

        if self.connection_window is not None:
            try:
                self.connection_window.show()
                return True
            except Exception:  # noqa: BLE001 - recreate a closed or invalid native window.
                self.connection_window = None

        self.connection_window = webview.create_window(
            "Settings",
            f"{self.base_url}/connect",
            width=560,
            height=650,
            min_size=(480, 560),
            resizable=True,
            js_api=ConnectionWindowApi(self),
        )
        self.connection_window.events.closed += self._connection_closed
        return True

    def close_connection_window(self) -> None:
        window = self.connection_window
        self.connection_window = None
        if window is not None:
            window.destroy()

    def _connection_closed(self, *_: Any) -> None:
        self.connection_window = None


class ConnectionWindowApi:
    """Methods exposed to the separate connection window."""

    def __init__(self, desktop_api: DesktopApi) -> None:
        self.desktop_api = desktop_api

    def close_connection_window(self) -> None:
        self.desktop_api.close_connection_window()

    def choose_download_directory(self, current_directory: str | None = None) -> str | None:
        return self.desktop_api.choose_download_directory(
            current_directory,
            self.desktop_api.connection_window,
        )

    def choose_config_directory(self, current_directory: str = ".") -> str | None:
        return self.desktop_api.choose_config_directory(
            current_directory,
            self.desktop_api.connection_window,
        )


def run_desktop(app: Any) -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("Install the desktop GUI dependencies: pip install -r requirements.txt") from exc

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    desktop_api = DesktopApi(base_url)
    window = webview.create_window(
        "GoPro Downloader",
        f"{base_url}/",
        width=1080,
        height=780,
        min_size=(760, 600),
        js_api=desktop_api,
    )
    desktop_api.main_window = window
    if not has_saved_cohn():
        desktop_api.open_connection_window()
    try:
        webview.start(debug=False)
    finally:
        server.shutdown()
        server_thread.join(timeout=2)
