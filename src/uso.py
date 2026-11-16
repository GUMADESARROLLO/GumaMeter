"""Uso de aplicaciones: qué programa está en primer plano y cuánto tiempo.

Solo se registra el **nombre del programa** (p. ej. ``chrome.exe`` / "Google Chrome") y los
segundos. Nunca títulos de ventana, páginas visitadas, teclas ni capturas de pantalla.

La app toma una muestra cada ``PASO`` segundos mientras hay sesión iniciada (en cualquier estado), la
acumula aquí y la envía al servidor junto con el latido (``POST /api/sac/uso``).
"""

from __future__ import annotations

import os
import sys
from typing import Callable

from inactividad import segundos_sin_actividad

PASO = 5  # segundos entre muestras
UMBRAL_INACTIVO = 300  # sin teclado ni mouse por 5 min = "sin actividad"
TOPE = 540  # segundos que se guardan como mucho si no hay conexión (el servidor acepta 600)
DESCONOCIDO = ("(desconocido)", "Desconocido")

# (proceso, nombre visible, segundos sin teclado ni mouse); proceso None = no hay ventana activa
Lectura = tuple[str | None, str | None, float]


class MedidorUso:
    """Acumula las muestras hasta que se envían. No depende de Qt ni de Windows."""

    def __init__(
        self,
        leer: Callable[[], Lectura] | None = None,
        paso: int = PASO,
        umbral: int = UMBRAL_INACTIVO,
        tope: int = TOPE,
    ):
        self._leer = leer or lectura_windows
        self._paso = paso
        self._umbral = umbral
        self._tope = tope
        self._apps: dict[str, list] = {}  # proceso -> [nombre, segundos]
        self._inactivo = 0

    def total(self) -> int:
        return self._inactivo + sum(a[1] for a in self._apps.values())

    def muestrear(self) -> None:
        if self.total() + self._paso > self._tope:
            return  # sin conexión por mucho rato: no se acumula más
        try:
            proceso, nombre, quieto = self._leer()
        except Exception:
            return
        if quieto >= self._umbral:
            self._inactivo += self._paso
        elif proceso:
            self._sumar(proceso, nombre or proceso, self._paso)

    def tomar(self) -> dict | None:
        """Entrega lo acumulado en el formato de la API y deja el medidor en cero."""
        if not self.total():
            return None
        carga = {
            "apps": [{"proceso": p, "nombre": a[0], "segundos": a[1]} for p, a in self._apps.items()],
            "inactivo": self._inactivo,
        }
        self.vaciar()
        return carga

    def devolver(self, carga: dict) -> None:
        """Reincorpora un envío que falló, para reintentarlo en el siguiente latido."""
        libre = self._tope - self.total()
        for a in carga.get("apps", []):
            seg = min(a["segundos"], libre)
            if seg > 0:
                self._sumar(a["proceso"], a["nombre"], seg)
                libre -= seg
        self._inactivo += max(0, min(carga.get("inactivo", 0), libre))

    def vaciar(self) -> None:
        self._apps = {}
        self._inactivo = 0

    def _sumar(self, proceso: str, nombre: str, segundos: int) -> None:
        if proceso in self._apps:
            self._apps[proceso][1] += segundos
        else:
            self._apps[proceso] = [nombre, segundos]


# -- lectura en Windows ---------------------------------------------------------

_nombres: dict[str, str] = {}  # ruta del .exe -> nombre visible


def lectura_windows() -> Lectura:
    if sys.platform != "win32":
        return None, None, 0.0
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32

    quieto = segundos_sin_actividad()

    user32.GetForegroundWindow.restype = wintypes.HWND
    ventana = user32.GetForegroundWindow()
    if not ventana:
        return None, None, quieto
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(ventana, ctypes.byref(pid))
    if not pid.value:
        return None, None, quieto

    kernel32.OpenProcess.restype = wintypes.HANDLE
    proceso = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not proceso:
        return (*DESCONOCIDO, quieto)  # p. ej. un programa abierto como administrador
    try:
        ruta = ctypes.create_unicode_buffer(1024)
        largo = wintypes.DWORD(len(ruta))
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        if not kernel32.QueryFullProcessImageNameW(proceso, 0, ruta, ctypes.byref(largo)):
            return (*DESCONOCIDO, quieto)
    finally:
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle(proceso)

    exe = os.path.basename(ruta.value).lower()
    if not exe:
        return (*DESCONOCIDO, quieto)
    if ruta.value not in _nombres:
        _nombres[ruta.value] = _descripcion(ruta.value) or _nombre_por_defecto(exe)
    return exe, _nombres[ruta.value], quieto


def _nombre_por_defecto(exe: str) -> str:
    base = exe[:-4] if exe.endswith(".exe") else exe
    return base[:1].upper() + base[1:]


def _descripcion(ruta: str) -> str | None:
    """"Descripción del archivo" del .exe (lo que muestra el Administrador de tareas)."""
    import ctypes
    from ctypes import wintypes

    version = ctypes.windll.version
    tam = version.GetFileVersionInfoSizeW(ruta, None)
    if not tam:
        return None
    datos = ctypes.create_string_buffer(tam)
    if not version.GetFileVersionInfoW(ruta, 0, tam, datos):
        return None
    puntero, largo = ctypes.c_void_p(), wintypes.UINT()
    if not version.VerQueryValueW(datos, "\\VarFileInfo\\Translation", ctypes.byref(puntero), ctypes.byref(largo)) or largo.value < 4:
        return None
    idioma, pagina = (ctypes.c_ushort * 2).from_address(puntero.value)
    clave = f"\\StringFileInfo\\{idioma:04x}{pagina:04x}\\FileDescription"
    if not version.VerQueryValueW(datos, clave, ctypes.byref(puntero), ctypes.byref(largo)) or not largo.value:
        return None
    texto = ctypes.wstring_at(puntero.value, largo.value).strip("\x00 ").strip()
    return texto[:150] or None
