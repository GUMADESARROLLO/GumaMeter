"""El cliente real contra el servidor simulado: comprueba que ambos siguen el mismo contrato."""

import threading

import pytest

import mock_api
from api import ClienteApi, DemasiadosIntentos, EstadoInvalido, NoAutorizado, Prohibido


@pytest.fixture
def servidor():
    srv = mock_api.crear_servidor(puerto=0, sin_senal=180)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_recorrido_completo(servidor):
    c = ClienteApi(servidor, reintentos=0)
    sesion = c.login("sac03", "1234", "PC-PRUEBA")
    assert sesion.usuario.username == "SAC03" and sesion.usuario.nombre == "Lucía Castro"
    assert sesion.estado.estado == "off"

    assert c.cambiar_estado("on").estado == "on"
    assert c.latido().estado == "on"
    assert c.obtener_estado().estado == "on"
    with pytest.raises(EstadoInvalido):
        c.cambiar_estado("volando")

    token = c.token
    c.logout()
    with pytest.raises(NoAutorizado):  # el token quedó revocado
        ClienteApi(servidor, token, reintentos=0).latido()

    # El logout dejó al usuario en Desconectado.
    assert ClienteApi(servidor, reintentos=0).login("SAC03", "1234", "PC").estado.estado == "off"


def test_sesion_unica_entrar_en_otro_equipo_cierra_el_anterior(servidor):
    a = ClienteApi(servidor, reintentos=0)
    b = ClienteApi(servidor, reintentos=0)
    a.login("SAC01", "1234", "PC-A")
    a.cambiar_estado("on")
    assert b.login("SAC01", "1234", "PC-B").estado.estado == "on"  # el estado se conserva

    with pytest.raises(NoAutorizado) as e:
        a.latido()
    assert "otro equipo" in e.value.mensaje and e.value.del_servidor
    assert b.latido().estado == "on"


def test_uso_de_aplicaciones(servidor):
    c = ClienteApi(servidor, reintentos=0)
    c.login("SAC01", "1234", "PC")
    c.enviar_uso([{"proceso": "Chrome.exe", "nombre": "Google Chrome", "segundos": 50}], 10)
    c.enviar_uso([{"proceso": "chrome.exe", "nombre": "Google Chrome", "segundos": 60}], 0)
    with pytest.raises(EstadoInvalido):  # 422: más segundos de los posibles en un envío
        c.enviar_uso([{"proceso": "chrome.exe", "nombre": "Google Chrome", "segundos": 601}], 0)


def test_solo_rol_sac(servidor):
    for usuario in ("VENTAS01", "SAC99"):
        with pytest.raises(Prohibido) as e:
            ClienteApi(servidor, reintentos=0).login(usuario, "1234", "PC")
        assert e.value.mensaje


def test_limite_de_intentos(servidor):
    c = ClienteApi(servidor, reintentos=0)
    for _ in range(mock_api.MAX_INTENTOS):
        with pytest.raises(NoAutorizado):
            c.login("SAC02", "mala", "PC")
    with pytest.raises(DemasiadosIntentos):
        c.login("SAC02", "1234", "PC")


def test_sin_senal_pasa_a_desconectado(servidor, monkeypatch):
    c = ClienteApi(servidor, reintentos=0)
    c.login("SAC01", "1234", "PC")
    c.cambiar_estado("on")

    real = mock_api.time.monotonic
    monkeypatch.setattr(mock_api.time, "monotonic", lambda: real() + 181)  # pasan 3 minutos
    assert c.obtener_estado().estado == "off"
