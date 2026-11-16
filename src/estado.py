"""Lógica del estado del usuario, sin Qt.

Regla central: el estado local **solo** cambia cuando el servidor lo confirma.
Si una llamada falla, el estado queda como estaba; la app nunca lo cambia por
su cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from api import (
    ClienteApi,
    ErrorApi,
    EstadoRemoto,
    NoAutorizado,
    Prohibido,
    SinConexion,
)


@dataclass(frozen=True)
class InfoEstado:
    clave: str
    etiqueta: str
    subtitulo: str


ESTADOS: dict[str, InfoEstado] = {
    "on": InfoEstado("on", "En línea", "Atendiendo pedidos"),
    "afk": InfoEstado("afk", "AFK", "Ausente un momento"),
    "lunch": InfoEstado("lunch", "Descanso", "Pausa programada"),
    "off": InfoEstado("off", "Desconectado", "Fuera de turno"),
}

MSG_NO_GUARDADO = "No se pudo guardar el estado. Revisa la conexión."
MSG_SESION_VENCIDA = "Tu sesión venció. Vuelve a iniciar sesión."


def etiqueta(estado: str | None) -> str:
    return ESTADOS[estado].etiqueta if estado in ESTADOS else "Sin estado"


def hora_corta(desde: str | None) -> str | None:
    """``"2026-11-16 08:15:42"`` -> ``"08:15"`` (ya viene en hora de Managua)."""
    if not desde or len(desde) < 16:
        return None
    return desde[11:16]


class ControladorEstado:
    """Mantiene el estado confirmado por el servidor y avisa de los cambios.

    Los avisos son funciones simples para que la capa Qt las conecte a señales:

    - ``al_cambiar_estado(estado, desde)``: el servidor confirmó un estado.
    - ``al_cambiar_conexion(conectado)``: se perdió o se recuperó la conexión.
    - ``al_invalidar_sesion(mensaje)``: 401 o 403; hay que volver al login.
    """

    def __init__(
        self,
        api: ClienteApi,
        *,
        al_cambiar_estado: Callable[[str, str | None], None] | None = None,
        al_cambiar_conexion: Callable[[bool], None] | None = None,
        al_invalidar_sesion: Callable[[str], None] | None = None,
    ):
        self.api = api
        self.estado: str | None = None
        self.desde: str | None = None
        self.conectado: bool | None = None  # None = todavía no se sabe
        self._al_cambiar_estado = al_cambiar_estado or (lambda e, d: None)
        self._al_cambiar_conexion = al_cambiar_conexion or (lambda c: None)
        self._al_invalidar_sesion = al_invalidar_sesion or (lambda m: None)

    # -- operaciones -------------------------------------------------------

    def iniciar(self, remoto: EstadoRemoto) -> None:
        """Estado que devolvió el login."""
        self._conexion(True)
        self._aplicar(remoto, forzar=True)

    def reiniciar(self) -> None:
        """Olvida todo (al cerrar sesión)."""
        self.estado = None
        self.desde = None
        self.conectado = None

    def cambiar(self, nuevo: str) -> bool:
        """Pide el cambio al servidor. Devuelve True solo si lo confirmó."""
        return self._llamar(lambda: self.api.cambiar_estado(nuevo))

    def latido(self) -> bool:
        """Señal de vida. Si el servidor cambió el estado, lo refleja."""
        return self._llamar(self.api.latido)

    def refrescar(self) -> bool:
        """Consulta el estado vigente sin enviar señal de vida."""
        return self._llamar(self.api.obtener_estado)

    # -- interno -----------------------------------------------------------

    def _llamar(self, llamada: Callable[[], EstadoRemoto]) -> bool:
        try:
            remoto = llamada()
        except NoAutorizado as e:
            # El servidor explica el motivo (p. ej. "iniciaste sesión en otro equipo")
            self._al_invalidar_sesion(e.mensaje if e.del_servidor else MSG_SESION_VENCIDA)
            return False
        except Prohibido as e:
            self._al_invalidar_sesion(e.mensaje)
            return False
        except SinConexion:
            self._conexion(False)
            return False
        except ErrorApi:
            # 422, 5xx…: el servidor respondió, pero no confirmó nada.
            return False
        self._conexion(True)
        self._aplicar(remoto)
        return True

    def _aplicar(self, remoto: EstadoRemoto, forzar: bool = False) -> None:
        if forzar or remoto.estado != self.estado or remoto.desde != self.desde:
            self.estado = remoto.estado
            self.desde = remoto.desde
            self._al_cambiar_estado(self.estado, self.desde)

    def _conexion(self, conectado: bool) -> None:
        if conectado != self.conectado:
            self.conectado = conectado
            self._al_cambiar_conexion(conectado)
