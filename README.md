# GoPro Downloader

A cross-platform desktop app that connects to a GoPro over Bluetooth Low Energy (BLE), configures Wi-Fi and COHN, and manages camera media over HTTPS. The interface runs in a native window powered by pywebview.

## Requirements

- Python 3.11–3.13 (Python 3.13 is recommended)
- A GoPro that supports Open GoPro API 2.0 and COHN
- A computer with Bluetooth LE and Wi-Fi
- The camera must be on. To access media, the computer and camera must be on the same Wi-Fi network.

COHN support depends on the camera model and firmware. BLE or Open GoPro support alone does not guarantee COHN support.

## Install and Run

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app
```

## Build with PyInstaller

Install the application and build dependencies in the active virtual environment, then build the native desktop bundle:

```bash
python -m pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller --noconfirm --clean gopro_downloader.spec
```

The build is written to `dist/`. On macOS it produces `GoPro Downloader.app`; on Windows and Linux it produces a `GoPro Downloader` folder containing the executable and its dependencies. Build separately on each target operating system. Linux also needs a pywebview renderer such as WebKit2GTK or Qt WebEngine installed on the target system.

For Python development, install the linter and formatter and run the configured checks:

```bash
ruff check .
ruff format --check .
```

## Application Overview

Flask serves the local interface, and pywebview displays it in a native window. The settings window opens at startup if the local COHN database does not contain complete credentials, or it can be opened with the gear icon. Settings let you connect the camera, choose the folder for the COHN database, certificate, and credentials, and choose a download folder.

Media is saved to `~/Downloads/GoPro/` by default. The application configuration folder defaults to `%APPDATA%/gopro-downloader` on Windows and `$XDG_CONFIG_HOME/gopro-downloader` (or `~/.config/gopro-downloader`) on Linux and macOS. Original downloads show percentage and transferred bytes, and can be cancelled.

The app sends native system notifications when an original download or a batch of downloads completes or fails. On macOS, launch `dist/GoPro Downloader.app` to let Notification Center identify the app and request permission; notifications may not work when running the development entry point with `python -m app`. The PyInstaller spec ad-hoc signs the app bundle. Windows and Linux use `desktop-notifier`.

Application code is organized under `app/`: startup, routes, background jobs, media operations, settings, COHN operations, and native-window management are separate modules. Templates are in `templates/`; stylesheets, scripts, and SVG icons are in `static/`. The main client script, `static/js/app.js`, connects the ES modules for shared API methods and state, themes, interface behavior, media, and background jobs.

On Linux, WebKit2GTK or Qt WebEngine may be required; see the [pywebview installation guide](https://pywebview.flowrl.com/guide/installation) for renderer dependencies. The local server binds only to `127.0.0.1` and stops when the window closes.

`requirements.txt` installs the current SDK from GoPro's official repository. PyPI hosts an older SDK release; this project uses official PR #918 for a coroutine error fix during Wi-Fi scanning.

## Connect a Camera

If BLE connection fails, put the GoPro in pairing mode (**Connections → Connect Device → GoPro Quik**), close GoPro Quik on your phone, and stop other apps connected to the camera. Discovering a camera's BLE advertisement does not guarantee that a connection has been established.

Wi-Fi details are requested only when needed. If valid credentials already exist, the app does not reconfigure Wi-Fi. Basic Auth credentials are secrets; on POSIX systems, the configuration folder is protected from other users.

## Manage Media

The camera's media list refreshes automatically when the app starts. Click the `i` icon beside a file to view its metadata. Click the download icon to save the original; once a file has been downloaded, an open icon appears beside it. Files are first written to a temporary file and are renamed only after the download completes successfully.

Documentation: [Open GoPro Python SDK](https://gopro.github.io/OpenGoPro/python_sdk/) and [COHN API](https://gopro.github.io/OpenGoPro/docs/ble/cohn/).
