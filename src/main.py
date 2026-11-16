"""SAC Estados: marca el estado de trabajo del equipo SAC desde la bandeja de Windows."""

from __future__ import annotations

import os
import platform
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog

import run_at_startup
import settings
import theme
from api import ClienteApi, ErrorApi, ErrorServidor, Sesion, SinConexion
from estado import MSG_NO_GUARDADO, ControladorEstado
from login_window import VentanaLogin
from single_instance import InstanciaUnica
from tray import Bandeja
from uso import PASO, MedidorUso
from widgets import DialogoConfiguracion, confirmar

LATIDO_MS = 60_000  # señal de vida cada 60 s
REINTENTO_MS = 15_000  # sin conexión se reintenta más seguido

MSG_SALIR = "Al salir dejarás de enviar señal y en unos minutos pasarás a Desconectado. ¿Salir?"


class Trabajador(QObject):
    """Hace las llamadas HTTP fuera del hilo de la interfaz, una a la vez."""

    login_ok = Signal(object)  # Sesion
    login_error = Signal(str)
    estado_cambiado = Signal(str, object)  # estado, desde
    conexion_cambiada = Signal(bool)
    sesion_invalida = Signal(str)
    cambio_terminado = Signal(bool)
    latido_terminado = Signal()
    logout_terminado = Signal()
    uso_terminado = Signal(bool, object)  # enviado, carga

    def __init__(self):
        super().__init__()
        self.api = ClienteApi("")
        self.ctrl = ControladorEstado(
            self.api,
            al_cambiar_estado=self.estado_cambiado.emit,
            al_cambiar_conexion=self.conexion_cambiada.emit,
            al_invalidar_sesion=self.sesion_invalida.emit,
        )

    @Slot(str, str)
    def configurar(self, servidor: str, token: str) -> None:
        self.api.servidor = servidor
        self.api.token = token or None
        self.ctrl.reiniciar()

    @Slot(str, str, str)
    def login(self, servidor: str, usuario: str, clave: str) -> None:
        self.api.servidor = servidor
        self.ctrl.reiniciar()
        try:
            sesion = self.api.login(usuario, clave, dispositivo=_nombre_equipo())
        except SinConexion:
            self.login_error.emit("No se pudo conectar con el servidor. Revisa la dirección en Configuración.")
            return
        except ErrorApi as e:
            self.login_error.emit(e.mensaje)
            return
        self.login_ok.emit(sesion)
        self.ctrl.iniciar(sesion.estado)

    @Slot(str)
    def cambiar(self, estado: str) -> None:
        self.cambio_terminado.emit(bool(self.api.token) and self.ctrl.cambiar(estado))

    @Slot()
    def latido(self) -> None:
        if self.api.token:
            self.ctrl.latido()
        self.latido_terminado.emit()

    @Slot()
    def refrescar(self) -> None:
        if self.api.token:
            self.ctrl.refrescar()

    @Slot(object)
    def uso(self, carga: dict) -> None:
        """Envía el uso de aplicaciones. Si no hay conexión, se devuelve para reintentar."""
        if not self.api.token:
            return
        try:
            self.api.enviar_uso(carga["apps"], carga["inactivo"])
        except (SinConexion, ErrorServidor):
            self.uso_terminado.emit(False, carga)
        except ErrorApi:
            self.uso_terminado.emit(True, carga)  # 401/403/422: reintentar no lo arregla
        else:
            self.uso_terminado.emit(True, carga)

    @Slot()
    def logout(self) -> None:
        if self.api.token:
            try:
                self.api.logout()
            except ErrorApi:
                pass  # sin conexión: el servidor lo resolverá por falta de señal
        self.ctrl.reiniciar()
        self.logout_terminado.emit()


def _nombre_equipo() -> str:
    return os.environ.get("COMPUTERNAME") or platform.node() or "equipo"


class Aplicacion(QObject):
    pedir_config = Signal(str, str)
    pedir_login = Signal(str, str, str)
    pedir_cambio = Signal(str)
    pedir_latido = Signal()
    pedir_refresco = Signal()
    pedir_logout = Signal()
    pedir_uso = Signal(object)

    def __init__(self, app: QApplication, instancia: InstanciaUnica):
        super().__init__()
        self.app = app
        self.cfg, primera_vez = settings.Config.cargar()
        if primera_vez:
            self.cfg.guardar()
        # Solo el .exe se registra solo; en desarrollo se hace desde el interruptor.
        if run_at_startup.es_ejecutable():
            run_at_startup.aplicar(self.cfg.iniciar_con_windows)

        self.sesion: settings.SesionGuardada | None = None
        self._latido_en_curso = False
        self._logout_en_curso = False
        self._salir_al_terminar = False
        self._estado: str | None = None
        self._conectado = False
        self.medidor = MedidorUso()

        self.login = VentanaLogin()
        self.bandeja = Bandeja(self)
        self.bandeja.menu.set_inicio_windows(self.cfg.iniciar_con_windows)

        # Hilo de trabajo
        self.hilo = QThread(self)
        self.trabajador = Trabajador()
        self.trabajador.moveToThread(self.hilo)
        t = self.trabajador
        self.pedir_config.connect(t.configurar)
        self.pedir_login.connect(t.login)
        self.pedir_cambio.connect(t.cambiar)
        self.pedir_latido.connect(t.latido)
        self.pedir_refresco.connect(t.refrescar)
        self.pedir_logout.connect(t.logout)
        self.pedir_uso.connect(t.uso)
        t.uso_terminado.connect(self._al_terminar_uso)
        t.login_ok.connect(self._al_entrar)
        t.login_error.connect(self.login.mostrar_error)
        t.estado_cambiado.connect(self._al_cambiar_estado)
        t.conexion_cambiada.connect(self._al_cambiar_conexion)
        t.sesion_invalida.connect(self._al_invalidar_sesion)
        t.cambio_terminado.connect(self._al_terminar_cambio)
        t.latido_terminado.connect(self._al_terminar_latido)
        t.logout_terminado.connect(self._al_terminar_logout)
        self.hilo.start()

        self.reloj = QTimer(self)
        self.reloj.setInterval(LATIDO_MS)
        self.reloj.timeout.connect(self._latir)

        # Uso de aplicaciones: una muestra cada pocos segundos, solo En línea o AFK
        self.reloj_uso = QTimer(self)
        self.reloj_uso.setInterval(PASO * 1000)
        self.reloj_uso.timeout.connect(self._muestrear)
        self.reloj_uso.start()

        # Interfaz
        self.login.entrar_pedido.connect(self._entrar)
        self.login.configuracion_pedida.connect(self._configurar)
        m = self.bandeja.menu
        m.estado_elegido.connect(self._elegir_estado)
        m.inicio_windows_cambiado.connect(self._cambiar_inicio_windows)
        m.configuracion_pedida.connect(self._configurar)
        m.cerrar_sesion_pedido.connect(self._cerrar_sesion)
        m.iniciar_sesion_pedido.connect(self.login.mostrar)
        m.salir_pedido.connect(self._salir)
        self.bandeja.menu_abierto.connect(self._al_abrir_menu)
        instancia.mostrar_pedido.connect(self._mostrar)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._al_cambiar_tema)

        self._arrancar()

    # -- arranque ----------------------------------------------------------

    def _arrancar(self) -> None:
        guardada = settings.cargar_sesion()
        if guardada and guardada.servidor == self.cfg.servidor:
            self._abrir_sesion(guardada)
            self._latir()  # avisa de inmediato y trae el estado vigente
        else:
            if guardada:
                settings.borrar_sesion()
            self.login.mostrar()

    def _abrir_sesion(self, sesion: settings.SesionGuardada) -> None:
        self.sesion = sesion
        self.pedir_config.emit(sesion.servidor, sesion.token)
        self.bandeja.set_sesion(sesion.nombre, sesion.username)
        self.reloj.start(LATIDO_MS)

    def _olvidar_sesion(self) -> None:
        self.sesion = None
        self._estado = None
        self._conectado = False
        self.medidor.vaciar()
        self.reloj.stop()
        settings.borrar_sesion()
        self.bandeja.menu.hide()
        self.bandeja.menu.set_guardando(None)
        self.bandeja.set_sesion(None, None)

    def _mostrar(self) -> None:
        """Otra ejecución de la app pidió mostrar esta."""
        if self.sesion:
            self.bandeja.mostrar_menu()
        else:
            self.login.mostrar()

    # -- inicio y cierre de sesión -----------------------------------------

    def _entrar(self, usuario: str, clave: str) -> None:
        self.pedir_login.emit(self.cfg.servidor, usuario, clave)

    def _al_entrar(self, sesion: Sesion) -> None:
        guardada = settings.SesionGuardada(
            token=sesion.token,
            nombre=sesion.usuario.nombre,
            username=sesion.usuario.username,
            servidor=self.cfg.servidor,
        )
        try:
            settings.guardar_sesion(guardada)
        except Exception:
            self.bandeja.notificar("No se pudo guardar la sesión en Windows. Tendrás que entrar de nuevo al reiniciar.")
        self.sesion = guardada
        self.bandeja.set_sesion(guardada.nombre, guardada.username)
        self.reloj.start(LATIDO_MS)
        self.login.hide()
        self.bandeja.notificar("Sesión iniciada. La app sigue en la bandeja, junto al reloj.", aviso=False)

    def _cerrar_sesion(self) -> None:
        if not self.sesion:
            return
        self._logout_en_curso = True
        self.pedir_logout.emit()  # el servidor pasa a Desconectado y revoca el token
        self._olvidar_sesion()
        self.login.mostrar()

    def _al_terminar_logout(self) -> None:
        self._logout_en_curso = False
        if self._salir_al_terminar:
            self._terminar()

    def _al_invalidar_sesion(self, mensaje: str) -> None:
        if not self.sesion:
            return
        self._olvidar_sesion()
        self.pedir_config.emit(self.cfg.servidor, "")
        self.login.mostrar(aviso=mensaje)

    # -- estado ------------------------------------------------------------

    def _elegir_estado(self, clave: str) -> None:
        if not self.sesion:
            return
        self.bandeja.menu.set_guardando(clave)
        self.pedir_cambio.emit(clave)

    def _al_terminar_cambio(self, confirmado: bool) -> None:
        self.bandeja.menu.set_guardando(None)
        if not self.sesion:
            return
        if confirmado:
            self.bandeja.menu.hide()
        else:
            self.bandeja.notificar(MSG_NO_GUARDADO)

    def _al_cambiar_estado(self, estado: str, desde) -> None:
        if self.sesion:
            self._estado = estado
            self.bandeja.set_estado(estado, desde)

    def _al_cambiar_conexion(self, conectado: bool) -> None:
        if not self.sesion:
            return
        self._conectado = conectado
        self.bandeja.set_conexion(conectado)
        self.reloj.setInterval(LATIDO_MS if conectado else REINTENTO_MS)

    def _latir(self) -> None:
        if self.sesion and not self._latido_en_curso:
            self._latido_en_curso = True
            self.pedir_latido.emit()
            carga = self.medidor.tomar()
            if carga:
                self.pedir_uso.emit(carga)

    def _muestrear(self) -> None:
        # Se mide en cualquier estado mientras haya sesión y el servidor esté al tanto.
        if self.sesion and self._conectado:
            self.medidor.muestrear()

    def _al_terminar_uso(self, enviado: bool, carga: dict) -> None:
        if not enviado and self.sesion:
            self.medidor.devolver(carga)

    def _al_terminar_latido(self) -> None:
        self._latido_en_curso = False
        self.bandeja.repintar()  # por si cambió el tema de la barra de tareas

    def _al_abrir_menu(self) -> None:
        if self.sesion:
            self.pedir_refresco.emit()

    # -- preferencias ------------------------------------------------------

    def _configurar(self) -> None:
        dlg = DialogoConfiguracion(self.cfg.servidor, self.cfg.iniciar_con_windows)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cambio_servidor = dlg.servidor() != self.cfg.servidor
        if cambio_servidor and self.sesion:
            # El token es del servidor anterior: se cierra esa sesión allá.
            self._logout_en_curso = True
            self.pedir_logout.emit()
            self._olvidar_sesion()
        self.cfg.servidor = dlg.servidor()
        self._cambiar_inicio_windows(dlg.iniciar_con_windows())  # también guarda
        self.bandeja.menu.set_inicio_windows(self.cfg.iniciar_con_windows)
        if not self.sesion:
            self.login.mostrar(aviso="Cambiaste el servidor. Inicia sesión de nuevo." if cambio_servidor else None)

    def _cambiar_inicio_windows(self, activo: bool) -> None:
        self.cfg.iniciar_con_windows = activo
        self.cfg.guardar()
        if not run_at_startup.aplicar(activo):
            self.bandeja.notificar("No se pudo cambiar el inicio con Windows.")

    def _al_cambiar_tema(self, *_args) -> None:
        self.login.aplicar_tema()
        self.bandeja.aplicar_tema()

    # -- salida ------------------------------------------------------------

    def _salir(self) -> None:
        # Salir no cambia el estado: el servidor lo resuelve por falta de señal.
        if self.sesion and not confirmar("¿Salir de SAC Estados?", MSG_SALIR, aceptar="Salir"):
            return
        if self._logout_en_curso:
            # Se espera (como mucho unos segundos) a que el cierre de sesión llegue al servidor.
            self._salir_al_terminar = True
            QTimer.singleShot(8000, self._terminar)
            return
        self._terminar()

    def _terminar(self) -> None:
        self.reloj.stop()
        self.reloj_uso.stop()
        self.bandeja.ocultar()
        self.login.hide()
        self.hilo.quit()
        self.hilo.wait(3000)
        self.app.quit()


def main() -> int:
    if sys.platform == "win32":
        import ctypes

        # Identidad propia en la barra de tareas y en las notificaciones.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Unimark.SACEstados")

    app = QApplication(sys.argv)
    app.setApplicationName(settings.NOMBRE_APP)
    app.setApplicationDisplayName(settings.NOMBRE_APP)
    app.setOrganizationName("Unimark S.A.")
    app.setQuitOnLastWindowClosed(False)

    instancia = InstanciaUnica()
    if instancia.avisar_a_la_primera():
        return 0  # ya estaba abierta: la primera muestra su menú
    instancia.escuchar()

    theme.cargar_fuentes()
    app.setFont(theme.fuente_base())
    app.setWindowIcon(theme.icono_app())

    aplicacion = Aplicacion(app, instancia)  # noqa: F841 (mantiene vivos los objetos)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
