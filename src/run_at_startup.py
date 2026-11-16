"""Inicio con Windows mediante ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``."""

from __future__ import annotations

import sys
from pathlib import Path

_CLAVE = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALOR = "GumaMeter"
_VALOR_ANTERIOR = "SAC Estados"  # nombre anterior de la app: su entrada se quita


def es_ejecutable() -> bool:
    """True cuando corre como ``GumaMeter.exe`` (no desde el código fuente)."""
    return bool(getattr(sys, "frozen", False))


def comando() -> str:
    if es_ejecutable():
        return f'"{sys.executable}"'
    principal = Path(__file__).resolve().parent / "main.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interprete = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interprete}" "{principal}"'


def activado() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CLAVE) as clave:
            winreg.QueryValueEx(clave, _VALOR)
            return True
    except OSError:
        return False


def activar() -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CLAVE) as clave:
        winreg.SetValueEx(clave, _VALOR, 0, winreg.REG_SZ, comando())


def desactivar() -> None:
    _quitar(_VALOR)


def _quitar(valor: str) -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CLAVE, 0, winreg.KEY_SET_VALUE) as clave:
            winreg.DeleteValue(clave, valor)
    except OSError:
        pass


def aplicar(activo: bool) -> bool:
    """Deja el registro como pide la preferencia. Devuelve False si no se pudo."""
    try:
        _quitar(_VALOR_ANTERIOR)
        if activo:
            activar()  # también corrige la ruta si el .exe se movió
        else:
            desactivar()
        return True
    except OSError:
        return False
