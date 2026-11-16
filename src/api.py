"""Cliente de la API SAC de Laravel.

Contrato (base ``{servidor}/api/sac``):

    POST /login    {username, password, dispositivo} -> {token, usuario, estado, desde, ahora}
    GET  /estado                                      -> {estado, desde, ahora}
    POST /estado   {estado}                           -> {estado, desde, ahora}
    POST /latido                                      -> {estado, desde, ahora}
    POST /logout                                      -> {ok: true}
    POST /uso      {apps:[{proceso,nombre,segundos}], inactivo} -> {ok: true}

Este módulo no depende de Qt, para poder probarlo solo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

ESTADOS_VALIDOS = ("on", "afk", "lunch", "off")

# Respuestas que vale la pena reintentar: el servidor o el proxy fallaron de paso.
_HTTP_REINTENTABLES = (502, 503, 504)


class ErrorApi(Exception):
    """Error base. ``mensaje`` es un texto en español apto para mostrar al usuario."""

    def __init__(self, mensaje: str, codigo: int | None = None, del_servidor: bool = False):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.del_servidor = del_servidor  # True si el texto vino en el campo "mensaje" de la respuesta


class SinConexion(ErrorApi):
    """No se pudo llegar al servidor (red caída, tiempo agotado, 502/503/504)."""


class NoAutorizado(ErrorApi):
    """HTTP 401: credenciales o token inválidos."""


class Prohibido(ErrorApi):
    """HTTP 403: el usuario no es SAC o está inactivo."""


class EstadoInvalido(ErrorApi):
    """HTTP 422: el estado enviado no es válido."""


class DemasiadosIntentos(ErrorApi):
    """HTTP 429: demasiados intentos de inicio de sesión."""


class ErrorServidor(ErrorApi):
    """Cualquier otra respuesta inesperada del servidor."""


@dataclass(frozen=True)
class EstadoRemoto:
    estado: str
    desde: str | None
    ahora: str | None


@dataclass(frozen=True)
class Usuario:
    id: int | str
    nombre: str
    username: str


@dataclass(frozen=True)
class Sesion:
    token: str
    usuario: Usuario
    estado: EstadoRemoto


_MENSAJES = {
    401: "Usuario o contraseña incorrectos.",
    403: "Tu usuario no tiene acceso a SAC Estados.",
    422: "El estado no es válido.",
    429: "Demasiados intentos. Espera un momento y vuelve a intentar.",
}
_ERRORES = {
    401: NoAutorizado,
    403: Prohibido,
    422: EstadoInvalido,
    429: DemasiadosIntentos,
}


def url_base(servidor: str) -> str:
    """``http://servidor/SAC/public`` -> ``http://servidor/SAC/public/api/sac``."""
    return servidor.strip().rstrip("/") + "/api/sac"


class ClienteApi:
    """Cliente síncrono. Se usa desde un solo hilo (el de trabajo)."""

    def __init__(
        self,
        servidor: str,
        token: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        reintentos: int = 2,
        espera: float = 0.6,
        dormir: Callable[[float], None] = time.sleep,
        timeout: float = 10.0,
    ):
        self.token = token
        self._reintentos = reintentos
        self._espera = espera
        self._dormir = dormir
        self._transport = transport
        self._timeout = httpx.Timeout(timeout, connect=5.0)
        self._http: httpx.Client | None = None
        self._servidor = ""
        self.servidor = servidor

    # -- configuración -----------------------------------------------------

    @property
    def servidor(self) -> str:
        return self._servidor

    @servidor.setter
    def servidor(self, valor: str) -> None:
        valor = valor.strip().rstrip("/")
        if valor == self._servidor and self._http is not None:
            return
        self._servidor = valor
        self.cerrar()
        self._http = httpx.Client(
            base_url=url_base(valor) if valor else "",
            timeout=self._timeout,
            transport=self._transport,
            headers={"Accept": "application/json"},
        )

    def cerrar(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    # -- rutas -------------------------------------------------------------

    def login(self, username: str, password: str, dispositivo: str) -> Sesion:
        datos = self._pedir(
            "POST",
            "/login",
            json={"username": username, "password": password, "dispositivo": dispositivo},
            autenticada=False,
        )
        try:
            u = datos["usuario"]
            sesion = Sesion(
                token=str(datos["token"]),
                usuario=Usuario(id=u["id"], nombre=str(u["nombre"]), username=str(u["username"])),
                estado=_estado_remoto(datos),
            )
        except (KeyError, TypeError) as e:
            raise ErrorServidor("El servidor respondió algo inesperado.") from e
        self.token = sesion.token
        return sesion

    def obtener_estado(self) -> EstadoRemoto:
        return _estado_remoto(self._pedir("GET", "/estado"))

    def cambiar_estado(self, estado: str) -> EstadoRemoto:
        return _estado_remoto(self._pedir("POST", "/estado", json={"estado": estado}))

    def latido(self) -> EstadoRemoto:
        return _estado_remoto(self._pedir("POST", "/latido"))

    def enviar_uso(self, apps: list[dict], inactivo: int) -> None:
        """Uso de aplicaciones acumulado desde el último envío (ver ``uso.py``)."""
        self._pedir("POST", "/uso", json={"apps": apps, "inactivo": inactivo})

    def logout(self) -> None:
        try:
            self._pedir("POST", "/logout")
        finally:
            self.token = None

    # -- transporte --------------------------------------------------------

    def _pedir(self, metodo: str, ruta: str, *, json: Any = None, autenticada: bool = True) -> dict:
        if not self._servidor or self._http is None:
            raise SinConexion("Falta configurar la dirección del servidor.")
        headers = {}
        if autenticada:
            if not self.token:
                raise NoAutorizado("No hay una sesión iniciada.", 401)
            headers["Authorization"] = f"Bearer {self.token}"

        intentos = self._reintentos + 1
        for intento in range(intentos):
            ultimo = intento == intentos - 1
            try:
                r = self._http.request(metodo, ruta, json=json, headers=headers)
            except (httpx.TransportError, httpx.InvalidURL) as e:
                if ultimo or isinstance(e, httpx.InvalidURL):
                    raise SinConexion("No se pudo conectar con el servidor.") from e
            else:
                if r.status_code not in _HTTP_REINTENTABLES:
                    return self._interpretar(r)
                if ultimo:
                    raise SinConexion("El servidor no está disponible.", r.status_code)
            self._dormir(self._espera * (2**intento))
        raise SinConexion("No se pudo conectar con el servidor.")  # pragma: no cover

    @staticmethod
    def _interpretar(r: httpx.Response) -> dict:
        try:
            datos = r.json()
        except ValueError:
            datos = None
        if not isinstance(datos, dict):
            datos = {}

        if r.status_code == 200:
            return datos

        mensaje = datos.get("mensaje")
        del_servidor = isinstance(mensaje, str) and bool(mensaje.strip())
        if not del_servidor:
            mensaje = _MENSAJES.get(r.status_code, f"Error del servidor ({r.status_code}).")
        raise _ERRORES.get(r.status_code, ErrorServidor)(mensaje, r.status_code, del_servidor)


def _estado_remoto(datos: dict) -> EstadoRemoto:
    estado = datos.get("estado")
    if estado not in ESTADOS_VALIDOS:
        raise ErrorServidor("El servidor respondió un estado desconocido.")
    return EstadoRemoto(estado=estado, desde=datos.get("desde"), ahora=datos.get("ahora"))
