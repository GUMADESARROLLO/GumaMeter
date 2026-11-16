"""Ventana de inicio de sesión, de dos columnas como el login web."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

import theme
from widgets import CampoTexto, boton, etiqueta


class VentanaLogin(QWidget):
    entrar_pedido = Signal(str, str)  # usuario, contraseña
    configuracion_pedida = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("ventana")
        self.setWindowTitle("SAC Estados")
        self.setWindowIcon(theme.icono_app())
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setFixedSize(720, 440)

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._panel_marca())
        raiz.addWidget(self._formulario(), 1)
        self.aplicar_tema()

    # -- construcción ------------------------------------------------------

    def _panel_marca(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panelMarca")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setFixedWidth(300)

        caja = QVBoxLayout(panel)
        caja.setContentsMargins(32, 36, 32, 32)
        caja.setSpacing(0)

        self._logo = QLabel()
        caja.addWidget(self._logo)
        caja.addStretch(1)

        acento = QFrame()
        acento.setObjectName("marcaAcento")
        acento.setFixedSize(36, 4)
        caja.addWidget(acento)
        caja.addSpacing(14)
        caja.addWidget(etiqueta("SAC", "marcaTitulo"))
        caja.addSpacing(2)
        texto = etiqueta("Servicio de Atención al Cliente", "marcaTexto")
        texto.setWordWrap(True)
        caja.addWidget(texto)
        return panel

    def _formulario(self) -> QWidget:
        form = QWidget()
        form.setObjectName("formulario")
        form.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        caja = QVBoxLayout(form)
        caja.setContentsMargins(44, 0, 44, 0)
        caja.setSpacing(0)
        caja.addStretch(1)

        caja.addWidget(etiqueta("Iniciar sesión", "titulo"))
        caja.addSpacing(4)
        caja.addWidget(etiqueta("Marca tu estado de trabajo sin abrir el navegador.", "subtitulo"))
        caja.addSpacing(18)

        self.error = etiqueta("", "error")
        self.aviso = etiqueta("", "aviso")
        for lbl in (self.error, self.aviso):
            lbl.setWordWrap(True)
            lbl.hide()
            caja.addWidget(lbl)

        caja.addSpacing(12)
        caja.addWidget(etiqueta("Usuario", "etiqueta"))
        caja.addSpacing(6)
        self.usuario = CampoTexto()
        self.usuario.setPlaceholderText("Tu usuario del sistema SAC")
        caja.addWidget(self.usuario)

        caja.addSpacing(14)
        caja.addWidget(etiqueta("Contraseña", "etiqueta"))
        caja.addSpacing(6)
        self.clave = CampoTexto()
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        caja.addWidget(self.clave)

        caja.addSpacing(20)
        self.boton_entrar = boton("Entrar", "primario")
        self.boton_entrar.setDefault(True)
        caja.addWidget(self.boton_entrar)

        caja.addSpacing(12)
        fila = QHBoxLayout()
        self.boton_config = boton("Configuración", "enlace")
        fila.addWidget(self.boton_config)
        fila.addStretch(1)
        caja.addLayout(fila)
        caja.addStretch(1)

        self.usuario.returnPressed.connect(self.clave.setFocus)
        self.clave.returnPressed.connect(self._enviar)
        self.boton_entrar.clicked.connect(self._enviar)
        self.boton_config.clicked.connect(self.configuracion_pedida)
        return form

    # -- comportamiento ----------------------------------------------------

    def aplicar_tema(self) -> None:
        self.setStyleSheet(theme.hoja_estilos(theme.paleta()))
        self._logo.setPixmap(theme.logo("logo-20-white.png", 62, self.devicePixelRatioF()))

    def mostrar(self, aviso: str | None = None) -> None:
        self.set_ocupado(False)
        self.clave.clear()
        self.error.hide()
        self.aviso.hide()
        if aviso:
            self.mostrar_aviso(aviso)
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()
        (self.clave if self.usuario.text() else self.usuario).setFocus()

    def mostrar_error(self, texto: str) -> None:
        self.aviso.hide()
        self.error.setText(texto)
        self.error.show()
        self.set_ocupado(False)
        self.clave.selectAll()
        self.clave.setFocus()

    def mostrar_aviso(self, texto: str) -> None:
        self.error.hide()
        self.aviso.setText(texto)
        self.aviso.show()

    def set_ocupado(self, ocupado: bool) -> None:
        self.usuario.setEnabled(not ocupado)
        self.clave.setEnabled(not ocupado)
        self.boton_entrar.setEnabled(not ocupado)
        self.boton_config.setEnabled(not ocupado)
        self.boton_entrar.setText("Entrando…" if ocupado else "Entrar")

    def _enviar(self) -> None:
        usuario = self.usuario.text().strip()
        clave = self.clave.text()
        if not usuario:
            self.mostrar_error("Escribe tu usuario.")
            self.usuario.setFocus()
            return
        if not clave:
            self.mostrar_error("Escribe tu contraseña.")
            return
        self.error.hide()
        self.aviso.hide()
        self.set_ocupado(True)
        self.entrar_pedido.emit(usuario, clave)

    def closeEvent(self, evento) -> None:
        # Cerrar la ventana no cierra la app: sigue en la bandeja.
        evento.ignore()
        self.hide()
