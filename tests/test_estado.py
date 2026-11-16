"""Lógica del estado: solo cambia cuando el servidor confirma."""

import httpx

from api import ClienteApi, EstadoRemoto
from estado import MSG_SESION_VENCIDA, ControladorEstado, etiqueta, hora_corta


class Servidor:
    """Servidor de mentira: guarda el estado y permite simular fallos."""

    def __init__(self, estado="on", desde="2026-11-16 08:00:00"):
        self.estado = estado
        self.desde = desde
        self.fallo = None  # None | "red" | código HTTP
        self.cuerpo_fallo = {}
        self.llamadas = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.llamadas.append((peticion.method, peticion.url.path.rsplit("/", 1)[1]))
        if self.fallo == "red":
            raise httpx.ConnectError("sin red")
        if self.fallo:
            return httpx.Response(self.fallo, json=self.cuerpo_fallo)
        if peticion.method == "POST" and peticion.url.path.endswith("/estado"):
            import json

            self.estado = json.loads(peticion.content)["estado"]
            self.desde = "2026-11-16 10:30:00"
        return httpx.Response(200, json={"estado": self.estado, "desde": self.desde, "ahora": "2026-11-16 10:30:05"})


def armar(servidor: Servidor):
    api = ClienteApi(
        "http://servidor/SAC/public", "tok", transport=httpx.MockTransport(servidor), reintentos=0, dormir=lambda s: None
    )
    avisos = {"estado": [], "conexion": [], "sesion": []}
    ctrl = ControladorEstado(
        api,
        al_cambiar_estado=lambda e, d: avisos["estado"].append((e, d)),
        al_cambiar_conexion=avisos["conexion"].append,
        al_invalidar_sesion=avisos["sesion"].append,
    )
    ctrl.iniciar(EstadoRemoto("on", "2026-11-16 08:00:00", "2026-11-16 08:00:00"))
    avisos["estado"].clear()
    avisos["conexion"].clear()
    return ctrl, avisos


def test_el_estado_cambia_cuando_el_servidor_confirma():
    ctrl, avisos = armar(Servidor())
    assert ctrl.cambiar("afk") is True
    assert ctrl.estado == "afk"
    assert avisos["estado"] == [("afk", "2026-11-16 10:30:00")]


def test_sin_conexion_el_estado_queda_como_estaba():
    servidor = Servidor()
    ctrl, avisos = armar(servidor)
    servidor.fallo = "red"

    assert ctrl.cambiar("lunch") is False
    assert ctrl.estado == "on"  # no se adelanta al servidor
    assert avisos["estado"] == []  # el ícono no se toca
    assert avisos["conexion"] == [False]


def test_un_error_del_servidor_tampoco_cambia_el_estado():
    servidor = Servidor()
    ctrl, avisos = armar(servidor)
    for codigo in (422, 500):
        servidor.fallo = codigo
        assert ctrl.cambiar("lunch") is False
    assert ctrl.estado == "on"
    assert avisos["estado"] == []


def test_se_muestra_el_estado_que_devuelve_el_servidor_no_el_pedido():
    servidor = Servidor()
    ctrl, _ = armar(servidor)

    def terco(peticion):
        return httpx.Response(200, json={"estado": "off", "desde": "2026-11-16 11:00:00", "ahora": "x"})

    ctrl.api = ClienteApi("http://s", "tok", transport=httpx.MockTransport(terco))
    assert ctrl.cambiar("on") is True
    assert ctrl.estado == "off"


def test_el_latido_detecta_un_cambio_hecho_en_el_servidor():
    servidor = Servidor()
    ctrl, avisos = armar(servidor)

    assert ctrl.latido() is True
    assert avisos["estado"] == []  # nada cambió: no se repinta

    # El supervisor (o la regla de 3 minutos) lo pasó a Desconectado.
    servidor.estado, servidor.desde = "off", "2026-11-16 09:45:00"
    assert ctrl.latido() is True
    assert ctrl.estado == "off"
    assert avisos["estado"] == [("off", "2026-11-16 09:45:00")]
    assert servidor.llamadas[-1] == ("POST", "latido")


def test_latido_sin_conexion_avisa_y_no_cambia_el_estado():
    servidor = Servidor(estado="afk")
    ctrl, avisos = armar(servidor)
    ctrl.latido()
    avisos["estado"].clear()

    servidor.fallo = "red"
    assert ctrl.latido() is False
    assert ctrl.latido() is False
    assert ctrl.estado == "afk"
    assert avisos["estado"] == []
    assert avisos["conexion"] == [False]  # avisa una sola vez

    servidor.fallo = None
    assert ctrl.latido() is True
    assert avisos["conexion"] == [False, True]
    assert ctrl.estado == "afk"


def test_401_invalida_la_sesion():
    servidor = Servidor()
    ctrl, avisos = armar(servidor)
    servidor.fallo = 401
    assert ctrl.latido() is False
    assert avisos["sesion"] == [MSG_SESION_VENCIDA]
    assert ctrl.estado == "on"


def test_401_muestra_el_motivo_del_servidor():
    servidor = Servidor()
    ctrl, avisos = armar(servidor)
    servidor.fallo = 401
    servidor.cuerpo_fallo = {"mensaje": "Tu sesión se cerró porque este usuario inició sesión en otro equipo."}
    assert ctrl.latido() is False
    assert avisos["sesion"] == ["Tu sesión se cerró porque este usuario inició sesión en otro equipo."]


def test_403_invalida_la_sesion_con_el_mensaje_del_servidor():
    servidor = Servidor()
    ctrl, avisos = armar(servidor)
    servidor.fallo = 403
    servidor.cuerpo_fallo = {"mensaje": "Tu usuario está inactivo."}
    assert ctrl.cambiar("afk") is False
    assert avisos["sesion"] == ["Tu usuario está inactivo."]


def test_refrescar_usa_get_estado():
    servidor = Servidor(estado="lunch", desde="2026-11-16 12:00:00")
    ctrl, avisos = armar(servidor)
    assert ctrl.refrescar() is True
    assert servidor.llamadas == [("GET", "estado")]
    assert avisos["estado"] == [("lunch", "2026-11-16 12:00:00")]


def test_textos():
    assert etiqueta("lunch") == "Descanso"
    assert hora_corta("2026-11-16 08:15:42") == "08:15"
    assert hora_corta(None) is None
