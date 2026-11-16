"""Ícono de la bandeja y su menú propio (no el menú nativo gris de Windows)."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import theme
from estado import ESTADOS, etiqueta as etiqueta_estado, hora_corta
from widgets import Interruptor, Punto, boton, etiqueta

# Espacio alrededor de la tarjeta para que quepa la sombra.
_MARGEN = (20, 12, 20, 34)


class FilaEstado(QFrame):
    """Opción tipo radio: punto de color, título, subtítulo y ✓ si está activa."""

    elegida = Signal(str)

    def __init__(self, clave: str):
        super().__init__()
        self.clave = clave
        self._info = ESTADOS[clave]
        self.setObjectName("fila")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(f"{self._info.etiqueta}: {self._info.subtitulo}")

        caja = QHBoxLayout(self)
        caja.setContentsMargins(12, 8, 12, 8)
        caja.setSpacing(12)
        self.punto = Punto(theme.paleta().estados[clave], 10)
        caja.addWidget(self.punto, 0, Qt.AlignmentFlag.AlignVCenter)

        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(etiqueta(self._info.etiqueta, "filaTitulo"))
        self.sub = etiqueta(self._info.subtitulo, "filaSub")
        textos.addWidget(self.sub)
        caja.addLayout(textos, 1)

        self.check = etiqueta("✓", "filaCheck")
        self.check.setFixedWidth(16)
        caja.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set_activa(False)

    def set_activa(self, activa: bool) -> None:
        self.setProperty("activa", "true" if activa else "false")
        self.check.setText("✓" if activa else "")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_guardando(self, guardando: bool) -> None:
        self.sub.setText("Guardando…" if guardando else self._info.subtitulo)

    def aplicar_tema(self) -> None:
        self.punto.set_color(theme.paleta().estados[self.clave])

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and self.rect().contains(evento.position().toPoint()):
            self.elegida.emit(self.clave)

    def keyPressEvent(self, evento) -> None:
        if evento.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.elegida.emit(self.clave)
        else:
            super().keyPressEvent(evento)


class MenuBandeja(QWidget):
    estado_elegido = Signal(str)
    inicio_windows_cambiado = Signal(bool)
    configuracion_pedida = Signal()
    cerrar_sesion_pedido = Signal()
    iniciar_sesion_pedido = Signal()
    salir_pedido = Signal()

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.oculto_en = 0.0
        self._estado: str | None = None
        self._desde: str | None = None
        self._conectado = True
        self._con_sesion = False
        self._guardando: str | None = None

        fuera = QVBoxLayout(self)
        fuera.setContentsMargins(*_MARGEN)
        self.tarjeta = QFrame()
        self.tarjeta.setObjectName("tarjeta")
        self.tarjeta.setFixedWidth(292)
        fuera.addWidget(self.tarjeta)

        self._sombra = QGraphicsDropShadowEffect(self.tarjeta)
        self._sombra.setBlurRadius(36)
        self._sombra.setOffset(0, 12)
        self.tarjeta.setGraphicsEffect(self._sombra)

        caja = QVBoxLayout(self.tarjeta)
        caja.setContentsMargins(8, 8, 8, 8)
        caja.setSpacing(2)

        # Encabezado
        cab = QVBoxLayout()
        cab.setContentsMargins(10, 8, 10, 8)
        cab.setSpacing(3)
        linea = QHBoxLayout()
        linea.setSpacing(6)
        self.nombre = etiqueta("", "menuNombre")
        self.usuario = etiqueta("", "menuUsuario")
        linea.addWidget(self.nombre)
        linea.addWidget(self.usuario)
        linea.addStretch(1)
        cab.addLayout(linea)

        linea2 = QHBoxLayout()
        linea2.setSpacing(6)
        self.punto = Punto(theme.COLOR_SIN_CONEXION, 8)
        self.desde_txt = etiqueta("", "menuDesde")
        self.hora = etiqueta("", "menuHora")
        self.hora.setFont(theme.fuente_numeros(15, 600))
        linea2.addWidget(self.punto, 0, Qt.AlignmentFlag.AlignVCenter)
        linea2.addWidget(self.desde_txt)
        linea2.addWidget(self.hora)
        linea2.addStretch(1)
        cab.addLayout(linea2)
        caja.addLayout(cab)

        self.aviso = etiqueta("Sin conexión. Reintentando…", "aviso")
        self.aviso.hide()
        caja.addWidget(self.aviso)

        self._div1 = self._divisor()
        caja.addWidget(self._div1)
        caja.addSpacing(2)

        self.filas: dict[str, FilaEstado] = {}
        for clave in ESTADOS:
            fila = FilaEstado(clave)
            fila.elegida.connect(self._al_elegir)
            self.filas[clave] = fila
            caja.addWidget(fila)

        caja.addSpacing(2)
        caja.addWidget(self._divisor())
        caja.addSpacing(2)

        inicio = QHBoxLayout()
        inicio.setContentsMargins(11, 6, 10, 6)
        inicio.addWidget(etiqueta("Iniciar con Windows", "accionTexto"))
        inicio.addStretch(1)
        self.interruptor = Interruptor()
        self.interruptor.cambiado.connect(self.inicio_windows_cambiado)
        inicio.addWidget(self.interruptor)
        caja.addLayout(inicio)

        self.b_config = self._accion("Configuración", self.configuracion_pedida)
        self.b_entrar = self._accion("Iniciar sesión", self.iniciar_sesion_pedido)
        self.b_cerrar = self._accion("Cerrar sesión", self.cerrar_sesion_pedido)
        self.b_salir = self._accion("Salir", self.salir_pedido)
        for b in (self.b_config, self.b_entrar, self.b_cerrar, self.b_salir):
            caja.addWidget(b)

        # Aviso permanente: el registro de aplicaciones no es oculto
        self._div3 = self._divisor()
        caja.addSpacing(2)
        caja.addWidget(self._div3)
        self.nota = etiqueta(
            "Mientras tengas la sesión iniciada, en cualquier estado, esta app registra qué programas usas y por cuánto tiempo. "
            "No guarda títulos, páginas ni capturas.",
            "menuNota",
        )
        self.nota.setWordWrap(True)
        self.nota.setContentsMargins(11, 8, 11, 6)
        caja.addWidget(self.nota)

        self.aplicar_tema()
        self._refrescar()

    # -- construcción ------------------------------------------------------

    @staticmethod
    def _divisor() -> QFrame:
        d = QFrame()
        d.setObjectName("divisor")
        return d

    def _accion(self, texto: str, senal) -> QWidget:
        b = boton(texto, "accion")

        def al_pulsar() -> None:
            self.hide()
            senal.emit()

        b.clicked.connect(al_pulsar)
        return b

    # -- datos -------------------------------------------------------------

    def set_sesion(self, nombre: str | None, username: str | None) -> None:
        self._con_sesion = nombre is not None
        self.nombre.setText(nombre or "GumaMeter")
        self.usuario.setText(f"· {username}" if username else "")
        if not self._con_sesion:
            self._estado = self._desde = None
            self._guardando = None
        self._refrescar()

    def set_estado(self, estado: str | None, desde: str | None) -> None:
        self._estado, self._desde = estado, desde
        self._refrescar()

    def set_conexion(self, conectado: bool) -> None:
        self._conectado = conectado
        self._refrescar()

    def set_guardando(self, clave: str | None) -> None:
        self._guardando = clave
        self._refrescar()

    def set_inicio_windows(self, activo: bool) -> None:
        self.interruptor.set_activo(activo)

    def aplicar_tema(self) -> None:
        pal = theme.paleta()
        self.setStyleSheet(theme.hoja_estilos(pal))
        self._sombra.setColor(QColor(*pal.sombra))
        for fila in self.filas.values():
            fila.aplicar_tema()
        self._refrescar()

    def _refrescar(self) -> None:
        pal = theme.paleta()
        sesion = self._con_sesion
        for clave, fila in self.filas.items():
            fila.setVisible(sesion)
            fila.set_activa(sesion and clave == self._estado)
            fila.set_guardando(clave == self._guardando)
            fila.setEnabled(self._guardando is None)
        self._div1.setVisible(sesion)
        self.b_cerrar.setVisible(sesion)
        self.b_entrar.setVisible(not sesion)
        self._div3.setVisible(sesion)
        self.nota.setVisible(sesion)
        self.aviso.setVisible(sesion and not self._conectado)

        if not sesion:
            self.punto.set_color(theme.COLOR_SIN_CONEXION)
            self.desde_txt.setText("Sin sesión iniciada")
            self.hora.setText("")
        elif self._estado is None:
            self.punto.set_color(theme.COLOR_SIN_CONEXION)
            self.desde_txt.setText("Conectando…")
            self.hora.setText("")
        else:
            self.punto.set_color(pal.estados[self._estado])
            hora = hora_corta(self._desde)
            self.desde_txt.setText(etiqueta_estado(self._estado) + (" desde" if hora else ""))
            self.hora.setText(hora or "")
        if self.isVisible():
            self.adjustSize()

    # -- eventos -----------------------------------------------------------

    def _al_elegir(self, clave: str) -> None:
        if self._guardando is not None:
            return
        if clave == self._estado and self._conectado:
            self.hide()
            return
        self.estado_elegido.emit(clave)

    def keyPressEvent(self, evento) -> None:
        if evento.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(evento)

    def hideEvent(self, evento) -> None:
        self.oculto_en = time.monotonic()
        super().hideEvent(evento)

    def mostrar_junto_a(self, icono: QRect) -> None:
        """Abre el menú pegado al ícono de la bandeja, sin salirse de la pantalla."""
        self.layout().activate()
        self.adjustSize()
        ancho, alto = self.width(), self.height()
        izq, arr, der, aba = _MARGEN

        if icono.isValid() and not icono.isEmpty():
            ancla = icono.center()
        else:
            ancla = QCursor.pos()
            icono = QRect(ancla, ancla)
        pantalla = QGuiApplication.screenAt(ancla) or QGuiApplication.primaryScreen()
        area = pantalla.availableGeometry()

        # La tarjeta (sin contar el margen de la sombra) queda centrada sobre el ícono.
        x = ancla.x() - ancho // 2
        y = icono.top() - 8 - (alto - aba)
        if y + arr < area.top():  # barra de tareas arriba: se abre hacia abajo
            y = icono.bottom() + 8 - arr
        x = max(area.left() + 8 - izq, min(x, area.right() - 8 - (ancho - der)))
        y = max(area.top() + 8 - arr, min(y, area.bottom() - 8 - (alto - aba)))
        self.move(QPoint(x, y))
        self.show()
        self.raise_()
        self.activateWindow()


class Bandeja(QObject):
    """Ícono junto al reloj. Refleja únicamente lo que confirma el servidor."""

    menu_abierto = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.menu = MenuBandeja()
        self.icono = QSystemTrayIcon(self)
        self.icono.activated.connect(self._al_activar)
        self._con_sesion = False
        self._estado: str | None = None
        self._conectado = True
        self._pintar()
        self.icono.show()

    # -- datos -------------------------------------------------------------

    def set_sesion(self, nombre: str | None, username: str | None) -> None:
        self._con_sesion = nombre is not None
        if not self._con_sesion:
            self._estado = None
            self._conectado = True
        self.menu.set_sesion(nombre, username)
        self.menu.set_conexion(self._conectado)
        self._pintar()

    def set_estado(self, estado: str | None, desde: str | None) -> None:
        self._estado = estado
        self.menu.set_estado(estado, desde)
        self._pintar()

    def set_conexion(self, conectado: bool) -> None:
        self._conectado = conectado
        self.menu.set_conexion(conectado)
        self._pintar()

    def aplicar_tema(self) -> None:
        self.menu.aplicar_tema()
        self._pintar()

    def notificar(self, texto: str, aviso: bool = True) -> None:
        tipo = QSystemTrayIcon.MessageIcon.Warning if aviso else QSystemTrayIcon.MessageIcon.Information
        self.icono.showMessage("GumaMeter", texto, tipo, 6000)

    def mostrar_menu(self) -> None:
        self.menu.mostrar_junto_a(self.icono.geometry())
        self.menu_abierto.emit()

    def repintar(self) -> None:
        self._pintar()

    def ocultar(self) -> None:
        self.menu.hide()
        self.icono.hide()

    # -- interno -----------------------------------------------------------

    def _pintar(self) -> None:
        if not self._con_sesion:
            self.icono.setIcon(theme.icono_bandeja(None))
            self.icono.setToolTip("GumaMeter · Sin sesión")
        elif self._estado is None:
            self.icono.setIcon(theme.icono_bandeja("?", conectado=False))
            self.icono.setToolTip("GumaMeter · " + ("Conectando…" if self._conectado else "Sin conexión"))
        elif not self._conectado:
            self.icono.setIcon(theme.icono_bandeja(self._estado, conectado=False))
            self.icono.setToolTip("GumaMeter · Sin conexión")
        else:
            self.icono.setIcon(theme.icono_bandeja(self._estado))
            self.icono.setToolTip("GumaMeter · " + etiqueta_estado(self._estado))

    def _al_activar(self, motivo: QSystemTrayIcon.ActivationReason) -> None:
        if motivo not in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            return
        # Un clic sobre el ícono con el menú abierto lo cierra (no lo reabre).
        if time.monotonic() - self.menu.oculto_en < 0.25:
            return
        self.mostrar_menu()
