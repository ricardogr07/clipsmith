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

for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "huggingface_hub", "cv2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["main.py"],
    pathex=[".", "src"],
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
        "ollama",       # thin HTTP client for local Ollama server — no binary data needed
        "typer",
        "rich",
        "rich.logging",
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pandas", "scipy", "matplotlib", "sklearn",
        "PIL", "tensorflow", "torch", "torchvision",
        "IPython", "ipykernel", "notebook", "jupyter",
        "pytest", "setuptools", "pip",
        "tkinter", "_tkinter", "tcl", "tk",
    ],
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
