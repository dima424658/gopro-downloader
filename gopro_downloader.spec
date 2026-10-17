"""PyInstaller spec for the GoPro Downloader desktop application."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

project_root = Path(SPECPATH)  # noqa: F821 - injected by PyInstaller
datas = [
    (str(project_root / "templates"), "templates"),
    (str(project_root / "static"), "static"),
]
binaries = []
hiddenimports = ["app.routes.camera", "app.routes.media", "app.routes.pages"]

# pywebview, Bleak, and Open GoPro load some platform modules dynamically.
# Open GoPro's demos are excluded: importing its GUI demo requires optional cv2.
for package in ("webview", "bleak", "desktop_notifier"):
    datas += collect_data_files(package)
    binaries += collect_dynamic_libs(package)
    hiddenimports += collect_submodules(package)

datas += collect_data_files("open_gopro")
binaries += collect_dynamic_libs("open_gopro")
hiddenimports += collect_submodules(
    "open_gopro",
    filter=lambda module: module != "open_gopro.demos" and not module.startswith("open_gopro.demos."),
)

if sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
elif sys.platform == "win32":
    hiddenimports += ["webview.platforms.winforms"]
else:
    hiddenimports += ["webview.platforms.qt"]

analysis = Analysis(  # noqa: F821 - injected by PyInstaller
    [str(project_root / "run_app.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["open_gopro.demos"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)  # noqa: F821 - injected by PyInstaller
executable = EXE(  # noqa: F821 - injected by PyInstaller
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GoPro Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    codesign_identity="-" if sys.platform == "darwin" else None,
)
collection = COLLECT(  # noqa: F821 - injected by PyInstaller
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="GoPro Downloader",
)

if sys.platform == "darwin":
    BUNDLE(  # noqa: F821 - injected by PyInstaller
        collection,
        name="GoPro Downloader.app",
        bundle_identifier="com.gopro.downloader",
        codesign_identity="-",
        info_plist={
            "CFBundleDisplayName": "GoPro Downloader",
            "NSUserNotificationAlertStyle": "alert",
            "NSBluetoothAlwaysUsageDescription": "GoPro Downloader uses Bluetooth to connect to your GoPro camera."
        },
    )
