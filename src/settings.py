"""Preferencias y sesión guardada.

- Preferencias (URL del servidor, iniciar con Windows): ``%APPDATA%\\SAC Estados\\config.json``.
- Token: Administrador de credenciales de Windows (``keyring``). Nunca en texto plano.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

NOMBRE_APP = "SAC Estados"
SERVIDOR_POR_DEFECTO = "http://sac.umk.local"

_SERVICIO = NOMBRE_APP
_CUENTA = "sesion"


def carpeta_config() -> Path:
    # SAC_ESTADOS_CONFIG permite aislar las pruebas y las ejecuciones de desarrollo.
    forzada = os.environ.get("SAC_ESTADOS_CONFIG")
    if forzada:
        return Path(forzada)
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / NOMBRE_APP


def recurso(*partes: str) -> str:
    """Ruta a un archivo de ``assets``, tanto en desarrollo como dentro del .exe."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return str(base.joinpath("assets", *partes))


@dataclass
class Config:
    servidor: str = SERVIDOR_POR_DEFECTO
    iniciar_con_windows: bool = True

    @classmethod
    def cargar(cls) -> tuple["Config", bool]:
        """Devuelve ``(config, es_primera_vez)``."""
        ruta = carpeta_config() / "config.json"
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(), True
        cfg = cls()
        if isinstance(datos, dict):
            if isinstance(datos.get("servidor"), str) and datos["servidor"].strip():
                cfg.servidor = datos["servidor"].strip()
            if isinstance(datos.get("iniciar_con_windows"), bool):
                cfg.iniciar_con_windows = datos["iniciar_con_windows"]
        return cfg, False

    def guardar(self) -> None:
        carpeta = carpeta_config()
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / "config.json"
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        temporal.replace(ruta)


# -- sesión (token) en el Administrador de credenciales ------------------------


@dataclass(frozen=True)
class SesionGuardada:
    token: str
    nombre: str
    username: str
    servidor: str


def _llavero():
    import keyring

    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring

        if not isinstance(keyring.get_keyring(), WinVaultKeyring):
            keyring.set_keyring(WinVaultKeyring())
    return keyring


def guardar_sesion(sesion: SesionGuardada) -> None:
    _llavero().set_password(_SERVICIO, _CUENTA, json.dumps(asdict(sesion), ensure_ascii=False))


def cargar_sesion() -> SesionGuardada | None:
    try:
        crudo = _llavero().get_password(_SERVICIO, _CUENTA)
        if not crudo:
            return None
        d = json.loads(crudo)
        return SesionGuardada(
            token=str(d["token"]),
            nombre=str(d.get("nombre", "")),
            username=str(d.get("username", "")),
            servidor=str(d.get("servidor", "")),
        )
    except Exception:
        return None


def borrar_sesion() -> None:
    try:
        _llavero().delete_password(_SERVICIO, _CUENTA)
    except Exception:
        pass
