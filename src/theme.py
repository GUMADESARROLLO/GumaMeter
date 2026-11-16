"""Identidad visual: paleta del sistema web SAC, fuentes, hoja de estilos e íconos."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)

from settings import recurso

FUENTE_TEXTO = "Archivo"
FUENTE_NUMEROS = "Barlow Condensed"


@dataclass(frozen=True)
class Paleta:
    oscuro: bool
    fondo: str
    superficie: str
    borde: str
    divisor: str
    tinta: str
    tinta2: str
    atenuado: str
    primario: str
    primario_hover: str
    primario_suave: str
    lateral_a: str
    lateral_b: str
    cian: str
    error_fondo: str
    error_texto: str
    aviso_fondo: str
    aviso_texto: str
    campo_borde: str
    campo_fondo: str
    activo_fondo: str
    activo_borde: str
    fila_hover: str
    sombra: tuple[int, int, int, int]
    estados: dict[str, str] = field(default_factory=dict)


CLARO = Paleta(
    oscuro=False,
    fondo="#F2F5FA",
    superficie="#FFFFFF",
    borde="#DDE3EE",
    divisor="#E8EDF5",
    tinta="#15204F",
    tinta2="#26336B",
    atenuado="#4A5878",
    primario="#2B3B9E",
    primario_hover="#1B2766",
    primario_suave="#E9EDFA",
    lateral_a="#2B3B9E",
    lateral_b="#3446B3",
    cian="#29B6E8",
    error_fondo="#FDE6E8",
    error_texto="#C42B3A",
    aviso_fondo="#FFF1D6",
    aviso_texto="#8A4B00",
    campo_borde="#D3DBE8",
    campo_fondo="#FFFFFF",
    activo_fondo="#EEF2FC",
    activo_borde="#D6DEF5",
    fila_hover="#F5F7FC",
    sombra=(21, 32, 79, 56),  # rgba(21,32,79,.22)
    # No cambiar: validados para daltonismo.
    estados={"on": "#178A4C", "afk": "#E39A12", "lunch": "#3446B3", "off": "#A9B3C6"},
)

OSCURO = Paleta(
    oscuro=True,
    fondo="#0B1120",
    superficie="#111A2E",
    borde="#1F2A44",
    divisor="#1A2439",
    tinta="#E6EAF2",
    tinta2="#C3CBDD",
    atenuado="#8F9BB3",
    primario="#5B6CE0",
    primario_hover="#4757C9",
    primario_suave="#1A2450",
    lateral_a="#141C4A",
    lateral_b="#1B2766",
    cian="#29B6E8",
    error_fondo="#3A1820",
    error_texto="#FF98A2",
    aviso_fondo="#3A2A0C",
    aviso_texto="#F3C673",
    campo_borde="#2A3757",
    campo_fondo="#0E1627",
    activo_fondo="#18234A",
    activo_borde="#2C3A75",
    fila_hover="#162038",
    sombra=(0, 0, 0, 140),
    estados={"on": "#15824A", "afk": "#B98626", "lunch": "#6F7FE6", "off": "#3A4766"},
)

COLOR_SIN_CONEXION = "#8F9BB3"


# -- tema de Windows -----------------------------------------------------------


def es_oscuro() -> bool:
    """Modo de las aplicaciones en Windows."""
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def barra_de_tareas_clara() -> bool:
    """La barra de tareas puede ser oscura aunque las apps estén en modo claro."""
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as clave:
                return bool(winreg.QueryValueEx(clave, "SystemUsesLightTheme")[0])
        except OSError:
            pass
    return not es_oscuro()


def paleta() -> Paleta:
    return OSCURO if es_oscuro() else CLARO


# -- fuentes -------------------------------------------------------------------


def cargar_fuentes() -> None:
    for archivo in (
        "Archivo-Regular.ttf",
        "Archivo-Medium.ttf",
        "Archivo-SemiBold.ttf",
        "Archivo-Bold.ttf",
        "Archivo-ExtraBold.ttf",
        "BarlowCondensed-SemiBold.ttf",
        "BarlowCondensed-Bold.ttf",
    ):
        QFontDatabase.addApplicationFont(recurso("fonts", archivo))


def fuente_base() -> QFont:
    f = QFont(FUENTE_TEXTO)
    f.setPixelSize(13)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def fuente_numeros(px: int = 15, peso: int = 600) -> QFont:
    f = QFont(FUENTE_NUMEROS)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(peso))
    return f


# -- hoja de estilos -----------------------------------------------------------


def hoja_estilos(p: Paleta) -> str:
    return f"""
* {{
    font-family: "{FUENTE_TEXTO}";
    font-size: 13px;
    color: {p.tinta};
    outline: none;
}}
QWidget#ventana, QDialog {{ background: {p.fondo}; }}
QWidget#formulario {{ background: {p.superficie}; }}
QWidget#panelMarca {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.lateral_a}, stop:1 {p.lateral_b});
}}
QLabel {{ background: transparent; }}
QLabel#marcaTitulo {{ color: #FFFFFF; font-size: 20px; font-weight: 800; }}
QLabel#marcaTexto {{ color: rgba(255,255,255,0.86); font-size: 13px; font-weight: 500; }}
QFrame#marcaAcento {{ background: {p.cian}; border-radius: 2px; }}
QLabel#titulo {{ font-size: 21px; font-weight: 800; color: {p.tinta}; }}
QLabel#subtitulo {{ color: {p.atenuado}; }}
QLabel#etiqueta {{ color: {p.tinta2}; font-size: 12px; font-weight: 600; }}
QLabel#ayuda {{ color: {p.atenuado}; font-size: 12px; }}
QLabel#error {{
    background: {p.error_fondo}; color: {p.error_texto};
    border-radius: 10px; padding: 9px 12px; font-weight: 500;
}}
QLabel#aviso {{
    background: {p.aviso_fondo}; color: {p.aviso_texto};
    border-radius: 10px; padding: 9px 12px; font-weight: 500;
}}

QLineEdit {{
    min-height: 38px; max-height: 38px;
    border: 1px solid {p.campo_borde}; border-radius: 10px;
    padding: 0 12px; background: {p.campo_fondo}; color: {p.tinta};
    selection-background-color: {p.primario}; selection-color: #FFFFFF;
}}
QLineEdit:focus {{ border: 1px solid {p.primario}; }}
QLineEdit:disabled {{ color: {p.atenuado}; }}

QPushButton {{ min-height: 40px; max-height: 40px; border-radius: 10px; padding: 0 18px; font-weight: 600; }}
QPushButton#primario {{ background: {p.primario}; color: #FFFFFF; border: none; }}
QPushButton#primario:hover {{ background: {p.primario_hover}; }}
QPushButton#primario:pressed {{ background: {p.primario_hover}; }}
QPushButton#primario:disabled {{ background: {p.campo_borde}; color: {p.atenuado}; }}
QPushButton#secundario {{ background: {p.superficie}; color: {p.tinta2}; border: 1px solid {p.campo_borde}; }}
QPushButton#secundario:hover {{ background: {p.primario_suave}; border-color: {p.activo_borde}; }}
QPushButton#enlace {{
    background: transparent; border: none; color: {p.primario};
    min-height: 24px; max-height: 24px; padding: 0 2px; font-weight: 600;
}}
QPushButton#enlace:hover {{ color: {p.primario_hover if not p.oscuro else p.tinta}; }}
QPushButton:focus {{ border: 1px solid {p.cian}; }}

/* Menú de la bandeja */
QFrame#tarjeta {{ background: {p.superficie}; border: 1px solid {p.borde}; border-radius: 14px; }}
QLabel#menuNombre {{ font-size: 14px; font-weight: 700; color: {p.tinta}; }}
QLabel#menuUsuario {{ color: {p.atenuado}; font-size: 12px; font-weight: 500; }}
QLabel#menuDesde {{ color: {p.atenuado}; font-size: 12px; }}
QLabel#menuHora {{ color: {p.tinta2}; }}
QFrame#divisor {{ background: {p.divisor}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#fila {{ border: 1px solid transparent; border-radius: 10px; background: transparent; }}
QFrame#fila:hover {{ background: {p.fila_hover}; }}
QFrame#fila[activa="true"] {{ background: {p.activo_fondo}; border: 1px solid {p.activo_borde}; }}
QLabel#filaTitulo {{ font-size: 13px; font-weight: 600; color: {p.tinta}; }}
QLabel#filaSub {{ font-size: 12px; color: {p.atenuado}; }}
QLabel#filaCheck {{ font-size: 14px; font-weight: 700; color: {p.primario}; }}
QPushButton#accion {{
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    min-height: 32px; max-height: 32px; padding: 0 10px;
    text-align: left; font-weight: 500; color: {p.tinta2};
}}
QPushButton#accion:hover {{ background: {p.fila_hover}; }}
QPushButton#accion:focus {{ border: 1px solid {p.activo_borde}; }}
QLabel#menuNota {{ font-size: 11px; color: {p.atenuado}; }}
QLabel#accionTexto {{ font-weight: 500; color: {p.tinta2}; }}
"""


# -- imágenes ------------------------------------------------------------------


def logo(nombre: str, alto: int, dpr: float = 1.0) -> QPixmap:
    """Logo escalado a ``alto`` px lógicos, nítido en pantallas de alta densidad."""
    original = QPixmap(recurso("images", nombre))
    pm = original.scaledToHeight(max(1, round(alto * dpr)), Qt.TransformationMode.SmoothTransformation)
    pm.setDevicePixelRatio(dpr)
    return pm


def icono_app() -> QIcon:
    return QIcon(recurso("icon.ico"))


@lru_cache(maxsize=4)
def _isotipo(blanco: bool, gris: bool) -> QImage:
    nombre = "logo-20-iso-white.png" if blanco else "logo-20-iso.png"
    img = QImage(recurso("images", nombre)).convertToFormat(QImage.Format.Format_ARGB32)
    if gris:
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha():
                    g = round(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
                    # Se mezcla hacia un gris medio para que se lea "apagado".
                    g = round(g * 0.45 + 150 * 0.55)
                    img.setPixelColor(x, y, QColor(g, g, g, round(c.alpha() * 0.8)))
    return img


def _dibujar_icono(lado: int, color_punto: str | None, blanco: bool, gris: bool) -> QPixmap:
    pm = QPixmap(lado, lado)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, lado, lado), _isotipo(blanco, gris))

    if color_punto:
        d = lado * 0.52
        hueco = max(1.0, lado * 0.07)
        x = y = lado - d
        # Hueco transparente alrededor del punto: lo separa del isotipo en cualquier fondo.
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Qt.GlobalColor.black)
        p.drawEllipse(QRectF(x - hueco, y - hueco, d + 2 * hueco, d + 2 * hueco))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setBrush(QColor(color_punto))
        if blanco:
            # Barra oscura: un filo claro mantiene visible el punto de "Desconectado".
            grosor = max(1.0, lado / 24)
            p.setPen(QPen(QColor(255, 255, 255, 110), grosor))
            m = grosor / 2
            p.drawEllipse(QRectF(x + m, y + m, d - 2 * m, d - 2 * m))
        else:
            p.drawEllipse(QRectF(x, y, d, d))
    p.end()
    return pm


def icono_bandeja(estado: str | None, conectado: bool = True) -> QIcon:
    """Isotipo con el punto del estado. ``estado=None`` = sin sesión (sin punto)."""
    barra_oscura = not barra_de_tareas_clara()
    colores = (OSCURO if barra_oscura else CLARO).estados
    gris = estado is not None and not conectado
    if estado is None:
        punto = None
    elif gris:
        punto = COLOR_SIN_CONEXION
    else:
        punto = colores.get(estado, COLOR_SIN_CONEXION)
    icono = QIcon()
    for lado in (16, 20, 24, 32, 40, 48, 64):
        icono.addPixmap(_dibujar_icono(lado, punto, barra_oscura, gris))
    return icono
