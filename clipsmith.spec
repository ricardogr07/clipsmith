# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for clipsmith Windows distribution.
# Build with: pyinstaller clipsmith.spec --clean
#
# Output: dist/clipsmith/ (directory mode — more reliable with ctranslate2/onnxruntime)
# After build, place ffmpeg.exe in dist/clipsmith/ before zipping.

from PyInstaller.utils.hooks import collect_all

datas = [("config.yaml", ".")]
binaries = []
hiddenimports = []

for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "huggingface_hub"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["src/clipsmith/cli.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        "pydantic",
        "pydantic_settings",
        "pydantic.v1",
        "yaml",
        "httpx",
        "anthropic",
        "openai",
        "typer",
        "rich",
        "rich.logging",
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="clipsmith",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="clipsmith",
)
