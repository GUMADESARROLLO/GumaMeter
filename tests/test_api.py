"""Cliente de la API: 200, 401, 403, 422, 429, sin conexión y reintento."""

import json

import httpx
import pytest

from api import (
    ClienteApi,
    DemasiadosIntentos,
    ErrorServidor,
    EstadoInvalido,
    NoAutorizado,
    Prohibido,
    SinConexion,
    url_base,
)

SERVIDOR = "http://servidor/SAC/public"
ESTADO_OK = {"estado": "on", "desde": "2026-11-16 08:15:00", "ahora": "2026-11-16 09:00:00"}


def cliente(manejador, token="tok", **kw):
    esperas = []
    c = ClienteApi(SERVIDOR, token, transport=httpx.MockTransport(manejador), dormir=esperas.append, **kw)
    c.esperas = esperas
    return c


def respuesta(codigo, cuerpo=None):
    return lambda peticion: httpx.Response(codigo, json=cuerpo if cuerpo is not None else {})


def test_url_base_quita_la_barra_final():
    assert url_base("http://servidor/SAC/public/") == "http://servidor/SAC/public/api/sac"


def test_login_200_devuelve_sesion_y_guarda_el_token():
    vistas = []

    def manejador(peticion):
        vistas.append(peticion)
        return httpx.Response(
            200,
            json={"token": "abc", "usuario": {"id": 3, "nombre": "Lucía Castro", "username": "SAC03"}, **ESTADO_OK},
        )

    c = cliente(manejador, token=None)
    sesion = c.login("SAC03", "1234", "PC-LUCIA")

    p = vistas[0]
    assert p.method == "POST" and str(p.url) == SERVIDOR + "/api/sac/login"
    assert json.loads(p.content) == {"username": "SAC03", "password": "1234", "dispositivo": "PC-LUCIA"}
    assert "authorization" not in p.headers
    assert sesion.token == "abc" and c.token == "abc"
    assert sesion.usuario.nombre == "Lucía Castro" and sesion.usuario.username == "SAC03"
    assert sesion.estado.estado == "on" and sesion.estado.desde == "2026-11-16 08:15:00"


def test_rutas_protegidas_envian_el_token_y_el_cuerpo_del_contrato():
    vistas = []

    def manejador(peticion):
        vistas.append(peticion)
        if peticion.url.path.endswith("/logout"):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json=ESTADO_OK)

    c = cliente(manejador)
    assert c.obtener_estado().estado == "on"
    assert c.cambiar_estado("afk").estado == "on"  # manda lo que diga el servidor
    assert c.latido().ahora == "2026-11-16 09:00:00"
    c.logout()

    assert [(p.method, p.url.path) for p in vistas] == [
        ("GET", "/SAC/public/api/sac/estado"),
        ("POST", "/SAC/public/api/sac/estado"),
        ("POST", "/SAC/public/api/sac/latido"),
        ("POST", "/SAC/public/api/sac/logout"),
    ]
    assert all(p.headers["authorization"] == "Bearer tok" for p in vistas)
    assert json.loads(vistas[1].content) == {"estado": "afk"}
    assert c.token is None  # el logout olvida el token


def test_enviar_uso_manda_programas_y_tiempo_sin_actividad():
    vistas = []

    def manejador(peticion):
        vistas.append(peticion)
        return httpx.Response(200, json={"ok": True})

    apps = [{"proceso": "chrome.exe", "nombre": "Google Chrome", "segundos": 52}]
    cliente(manejador).enviar_uso(apps, 8)
    p = vistas[0]
    assert (p.method, p.url.path) == ("POST", "/SAC/public/api/sac/uso")
    assert json.loads(p.content) == {"apps": apps, "inactivo": 8}
    assert p.headers["authorization"] == "Bearer tok"


def test_desde_puede_ser_null():
    c = cliente(respuesta(200, {"estado": "off", "desde": None, "ahora": "2026-11-16 09:00:00"}))
    assert c.obtener_estado().desde is None


def test_401_es_no_autorizado():
    with pytest.raises(NoAutorizado) as e:
        cliente(respuesta(401)).latido()
    assert e.value.codigo == 401


def test_403_trae_el_mensaje_del_servidor():
    c = cliente(respuesta(403, {"mensaje": "Esta aplicación es solo para usuarios de SAC."}), token=None)
    with pytest.raises(Prohibido) as e:
        c.login("VENTAS01", "1234", "PC")
    assert e.value.mensaje == "Esta aplicación es solo para usuarios de SAC."


def test_422_es_estado_invalido():
    with pytest.raises(EstadoInvalido):
        cliente(respuesta(422)).cambiar_estado("volando")


def test_429_es_demasiados_intentos():
    with pytest.raises(DemasiadosIntentos) as e:
        cliente(respuesta(429), token=None).login("SAC03", "mala", "PC")
    assert "intentos" in e.value.mensaje.lower()


def test_los_errores_4xx_no_se_reintentan():
    llamadas = []

    def manejador(peticion):
        llamadas.append(1)
        return httpx.Response(401)

    with pytest.raises(NoAutorizado):
        cliente(manejador).latido()
    assert len(llamadas) == 1


def test_sin_conexion_tras_agotar_los_reintentos():
    llamadas = []

    def manejador(peticion):
        llamadas.append(1)
        raise httpx.ConnectError("sin red")

    c = cliente(manejador, reintentos=2, espera=0.5)
    with pytest.raises(SinConexion):
        c.latido()
    assert len(llamadas) == 3  # 1 intento + 2 reintentos
    assert c.esperas == [0.5, 1.0]  # espera creciente entre intentos


def test_reintento_se_recupera_de_un_corte_breve():
    llamadas = []

    def manejador(peticion):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise httpx.ReadTimeout("lento")
        if len(llamadas) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json=ESTADO_OK)

    assert cliente(manejador).cambiar_estado("on").estado == "on"
    assert len(llamadas) == 3


def test_503_persistente_cuenta_como_sin_conexion():
    with pytest.raises(SinConexion):
        cliente(respuesta(503)).latido()


def test_estado_desconocido_es_error_del_servidor():
    with pytest.raises(ErrorServidor):
        cliente(respuesta(200, {"estado": "bailando", "desde": None, "ahora": None})).latido()


def test_500_con_html_es_error_del_servidor():
    with pytest.raises(ErrorServidor):
        cliente(lambda p: httpx.Response(500, text="<h1>Error</h1>")).latido()


def test_sin_token_no_llama_al_servidor():
    llamadas = []
    c = cliente(lambda p: llamadas.append(1) or httpx.Response(200, json=ESTADO_OK), token=None)
    with pytest.raises(NoAutorizado):
        c.latido()
    assert llamadas == []
