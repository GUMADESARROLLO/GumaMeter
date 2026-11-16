"""Cambios de estado automáticos por inactividad (sin teclado ni mouse).

- En línea y ``UMBRAL_AFK`` sin actividad  -> la app pide AFK.
- En línea o AFK y ``UMBRAL_OFF`` sin actividad -> la app pide Desconectado.
- Si el AFK lo puso la app y vuelve la actividad -> la app pide En línea.

Descanso y Desconectado no se tocan. Un AFK elegido a mano no vuelve solo a En línea
(pero sí pasa a Desconectado al llegar a ``UMBRAL_OFF``). Tras una desconexión por
inactividad, la persona marca En línea a mano.

Aquí solo se **decide**; el cambio lo sigue confirmando el servidor (ver ``estado.py``).
"""

from __future__ import annotations

import sys

UMBRAL_AFK = 7 * 60  # segundos sin actividad para pasar a AFK
UMBRAL_OFF = 25 * 60  # segundos sin actividad para pasar a Desconectado
ESPERA_TRAS_FALLO = 30  # segundos antes de reintentar un cambio que el servidor no confirmó

# Motivos que se envían al servidor junto con el cambio
INACTIVIDAD = "inactividad"
REGRESO = "regreso"

MSG_AFK = "Pasaste a AFK por inactividad. Al volver a usar el equipo regresas a En línea."
MSG_OFF = "Pasaste a Desconectado por inactividad. Marca En línea cuando vuelvas."
MSG_SIGUES_OFF = "Estás Desconectado por inactividad. Marca En línea para continuar."


class Vigilante:
    """Decide los cambios automáticos. No depende de Qt ni de Windows."""

    def __init__(self, umbral_afk: int = UMBRAL_AFK, umbral_off: int = UMBRAL_OFF):
        self.umbral_afk = umbral_afk
        self.umbral_off = umbral_off
        self.afk_auto = False  # el AFK vigente lo puso la app
        self.off_auto = False  # el Desconectado vigente lo puso la app (falta avisar al volver)

    def decidir(self, estado: str | None, quieto: float) -> tuple[str, str] | None:
        """Cambio a pedir como ``(estado, motivo)``, o None si no toca hacer nada."""
        if estado != "afk":
            self.afk_auto = False
        if estado != "off":
            self.off_auto = False
        if estado not in ("on", "afk"):
            return None
        if quieto >= self.umbral_off:
            return "off", INACTIVIDAD
        if estado == "on" and quieto >= self.umbral_afk:
            return "afk", INACTIVIDAD
        if estado == "afk" and self.afk_auto and quieto < self.umbral_afk:
            return "on", REGRESO
        return None

    def confirmado(self, estado: str) -> None:
        """El servidor confirmó un cambio automático."""
        self.afk_auto = estado == "afk"
        self.off_auto = estado == "off"

    def manual(self) -> None:
        """La persona eligió un estado en el menú: lo automático deja de aplicar."""
        self.afk_auto = False
        self.off_auto = False

    def volvio_tras_desconexion(self, estado: str | None, quieto: float) -> bool:
        """True una sola vez: hay actividad de nuevo y sigue Desconectado por inactividad."""
        if estado == "off" and self.off_auto and quieto < self.umbral_afk:
            self.off_auto = False
            return True
        return False


def segundos_sin_actividad() -> float:
    """Segundos desde la última tecla o movimiento del mouse (0 fuera de Windows)."""
    if sys.platform != "win32":
        return 0.0
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0
