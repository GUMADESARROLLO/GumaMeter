"""Piezas de interfaz compartidas: punto de estado, interruptor, campo y diálogos."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import theme


class Punto(QWidget):
    """Círculo del color del estado."""

    def __init__(self, color: str, diametro: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(diametro, diametro)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(0, 0, self.width(), self.height()))


class Interruptor(QWidget):
    """Interruptor tipo píldora (reemplaza la casilla gris de Windows)."""

    cambiado = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._activo = False
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setFixedSize(QSize(34, 20))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName("Iniciar con Windows")

    def activo(self) -> bool:
        return self._activo

    def set_activo(self, valor: bool, animar: bool = False) -> None:
        self._activo = bool(valor)
        destino = 1.0 if self._activo else 0.0
        self._anim.stop()
        if animar:
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(destino)
            self._anim.start()
        else:
            self._pos = destino
            self.update()

    def alternar(self) -> None:
        self.set_activo(not self._activo, animar=True)
        self.cambiado.emit(self._activo)

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float) -> None:
        self._pos = v
        self.update()

    pos = Property(float, _get_pos, _set_pos)

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and self.rect().contains(evento.position().toPoint()):
            self.alternar()

    def keyPressEvent(self, evento) -> None:
        if evento.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.alternar()
        else:
            super().keyPressEvent(evento)

    def paintEvent(self, _evento) -> None:
        pal = theme.paleta()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        apagado, encendido = QColor(pal.campo_borde), QColor(pal.primario)
        t = self._pos
        pista = QColor(
            round(apagado.red() + (encendido.red() - apagado.red()) * t),
            round(apagado.green() + (encendido.green() - apagado.green()) * t),
            round(apagado.blue() + (encendido.blue() - apagado.blue()) * t),
        )
        p.setBrush(pista)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), self.height() / 2, self.height() / 2)
        d = self.height() - 6
        x = 3 + (self.width() - d - 6) * t
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 3, d, d))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QColor(pal.cian))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), self.height() / 2, self.height() / 2)


class CampoTexto(QLineEdit):
    """Campo con halo suave del color primario al enfocarlo."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._halo = QGraphicsDropShadowEffect(self)
        self._halo.setOffset(0, 0)
        self._halo.setBlurRadius(14)
        self._halo.setEnabled(False)
        self.setGraphicsEffect(self._halo)

    def focusInEvent(self, evento) -> None:
        color = QColor(theme.paleta().primario)
        color.setAlpha(95)
        self._halo.setColor(color)
        self._halo.setEnabled(True)
        super().focusInEvent(evento)

    def focusOutEvent(self, evento) -> None:
        self._halo.setEnabled(False)
        super().focusOutEvent(evento)


def etiqueta(texto: str, nombre: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setObjectName(nombre)
    return lbl


def boton(texto: str, nombre: str) -> QPushButton:
    b = QPushButton(texto)
    b.setObjectName(nombre)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def _preparar_dialogo(dlg: QDialog, titulo: str) -> None:
    dlg.setWindowTitle(titulo)
    dlg.setWindowIcon(theme.icono_app())
    dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dlg.setStyleSheet(theme.hoja_estilos(theme.paleta()))


def confirmar(titulo: str, mensaje: str, aceptar: str, cancelar: str = "Cancelar") -> bool:
    """Diálogo de confirmación con el estilo de la app. El foco inicial va en Cancelar."""
    dlg = QDialog()
    _preparar_dialogo(dlg, "GumaMeter")
    dlg.setFixedWidth(380)

    caja = QVBoxLayout(dlg)
    caja.setContentsMargins(24, 22, 24, 20)
    caja.setSpacing(8)
    t = etiqueta(titulo, "titulo")
    t.setStyleSheet("font-size: 17px;")
    m = etiqueta(mensaje, "subtitulo")
    m.setWordWrap(True)
    caja.addWidget(t)
    caja.addWidget(m)
    caja.addSpacing(12)

    fila = QHBoxLayout()
    fila.setSpacing(10)
    b_no = boton(cancelar, "secundario")
    b_si = boton(aceptar, "primario")
    b_no.clicked.connect(dlg.reject)
    b_si.clicked.connect(dlg.accept)
    fila.addStretch(1)
    fila.addWidget(b_no)
    fila.addWidget(b_si)
    caja.addLayout(fila)

    b_no.setDefault(True)
    b_no.setFocus()
    return dlg.exec() == QDialog.DialogCode.Accepted


class DialogoConfiguracion(QDialog):
    """URL del servidor e inicio con Windows."""

    def __init__(self, servidor: str, iniciar_con_windows: bool, parent: QWidget | None = None):
        super().__init__(parent)
        _preparar_dialogo(self, "Configuración · GumaMeter")
        self.setFixedWidth(430)

        caja = QVBoxLayout(self)
        caja.setContentsMargins(24, 22, 24, 20)
        caja.setSpacing(6)

        dpr = self.devicePixelRatioF()
        marca = QLabel()
        marca.setPixmap(theme.logo("logo-20-white.png" if theme.es_oscuro() else "logo-20.png", 34, dpr))
        caja.addWidget(marca)
        caja.addSpacing(10)

        t = etiqueta("Configuración", "titulo")
        t.setStyleSheet("font-size: 17px;")
        caja.addWidget(t)
        caja.addSpacing(8)

        caja.addWidget(etiqueta("Dirección del servidor", "etiqueta"))
        self.campo = CampoTexto()
        self.campo.setText(servidor)
        self.campo.setPlaceholderText("http://sac.umk.local")
        caja.addWidget(self.campo)
        caja.addWidget(etiqueta("La app usará esta dirección seguida de /api/sac.", "ayuda"))

        self.error = etiqueta("", "error")
        self.error.setWordWrap(True)
        self.error.hide()
        caja.addSpacing(4)
        caja.addWidget(self.error)
        caja.addSpacing(10)

        fila_inicio = QHBoxLayout()
        fila_inicio.addWidget(etiqueta("Iniciar con Windows", "accionTexto"))
        fila_inicio.addStretch(1)
        self.interruptor = Interruptor()
        self.interruptor.set_activo(iniciar_con_windows)
        fila_inicio.addWidget(self.interruptor)
        caja.addLayout(fila_inicio)
        caja.addSpacing(16)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        b_no = boton("Cancelar", "secundario")
        b_si = boton("Guardar", "primario")
        b_si.setDefault(True)
        b_no.clicked.connect(self.reject)
        b_si.clicked.connect(self._guardar)
        fila.addStretch(1)
        fila.addWidget(b_no)
        fila.addWidget(b_si)
        caja.addLayout(fila)

    def servidor(self) -> str:
        return self.campo.text().strip().rstrip("/")

    def iniciar_con_windows(self) -> bool:
        return self.interruptor.activo()

    def _guardar(self) -> None:
        url = self.servidor()
        if not (url.startswith("http://") or url.startswith("https://")) or len(url) < 10:
            self.error.setText("Escribe la dirección completa, empezando por http:// o https://")
            self.error.show()
            self.campo.setFocus()
            return
        self.accept()
