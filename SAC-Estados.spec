# -*- mode: python ; coding: utf-8 -*-
# Genera un solo dist\SAC-Estados.exe, sin consola.  Uso: pyinstaller SAC-Estados.spec

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("assets/fonts/*.ttf", "assets/fonts"),
        ("assets/images/*.png", "assets/images"),
        ("assets/icon.ico", "assets"),
    ],
    hiddenimports=["keyring.backends.Windows", "win32ctypes.core.ctypes"],
    hookspath=[],
    runtime_hooks=[],
    # Módulos de Qt que la app no usa: reducen el tamaño del .exe.
    excludes=[
        "tkinter",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtPdf",
        "PySide6.QtSvg",
        "PySide6.QtOpenGL",
        "PySide6.QtDBus",
        "PIL",
        "pytest",
    ],
    noarchive=False,
)

# OpenSSL: debe ir el que trae Python junto a _ssl.pyd. Si en C:\Windows\System32
# hay otra copia más vieja (la instalan otros programas), PyInstaller puede tomar
# esa y el .exe falla al arrancar con "DLL load failed while importing _ssl".
import os
import sys

_dlls_python = os.path.join(sys.base_prefix, "DLLs")


def _openssl_de_python(entrada):
    destino, origen, tipo = entrada
    nombre = os.path.basename(destino).lower()
    if nombre.startswith(("libssl-", "libcrypto-")):
        propio = os.path.join(_dlls_python, os.path.basename(destino))
        if os.path.exists(propio):
            return (destino, propio, tipo)
    return entrada


a.binaries = [_openssl_de_python(b) for b in a.binaries]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SAC-Estados",
    icon="assets/icon.ico",
    console=False,
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
)
