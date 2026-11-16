"""Cambios automáticos por inactividad: cuándo se piden y cuándo no."""

import json

import httpx

from api import ClienteApi
from inactividad import INACTIVIDAD, REGRESO, UMBRAL_AFK, UMBRAL_OFF, Vigilante

MIN = 60


def test_umbrales_acordados():
    assert (UMBRAL_AFK, UMBRAL_OFF) == (7 * MIN, 25 * MIN)


def test_en_linea_pasa_a_afk_a_los_7_minutos():
    v = Vigilante()
    assert v.decidir("on", 7 * MIN - 1) is None
    assert v.decidir("on", 7 * MIN) == ("afk", INACTIVIDAD)


def test_afk_automatico_vuelve_a_en_linea_con_actividad():
    v = Vigilante()
    v.confirmado("afk")
    assert v.decidir("afk", 10 * MIN) is None  # sigue sin actividad
    assert v.decidir("afk", 2) == ("on", REGRESO)


def test_afk_manual_no_vuelve_solo():
    v = Vigilante()
    assert v.decidir("afk", 2) is None
    v.confirmado("afk")
    v.manual()  # la persona eligió AFK en el menú
    assert v.decidir("afk", 2) is None


def test_a_los_25_minutos_se_desconecta_desde_afk_o_en_linea():
    v = Vigilante()
    assert v.decidir("afk", 25 * MIN - 1) is None
    assert v.decidir("afk", 25 * MIN) == ("off", INACTIVIDAD)
    assert v.decidir("on", 25 * MIN) == ("off", INACTIVIDAD)


def test_descanso_y_desconectado_no_se_tocan():
    v = Vigilante()
    for estado in ("lunch", "off", None):
        assert v.decidir(estado, 60 * MIN) is None
        assert v.decidir(estado, 0) is None


def test_tras_desconexion_automatica_no_vuelve_solo_y_avisa_una_vez():
    v = Vigilante()
    v.confirmado("off")
    assert v.decidir("off", 30 * MIN) is None
    assert v.volvio_tras_desconexion("off", 30 * MIN) is False  # todavía no vuelve
    assert v.decidir("off", 1) is None  # hay actividad, pero En línea se marca a mano
    assert v.volvio_tras_desconexion("off", 1) is True
    assert v.volvio_tras_desconexion("off", 1) is False


def test_si_el_estado_cambia_por_otra_via_se_olvida_lo_automatico():
    v = Vigilante()
    v.confirmado("afk")
    assert v.decidir("lunch", 2) is None  # p. ej. eligió Descanso
    assert v.decidir("afk", 2) is None  # este AFK ya no es el automático


def test_el_motivo_viaja_solo_en_los_cambios_automaticos():
    cuerpos = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        cuerpos.append(json.loads(peticion.content))
        return httpx.Response(200, json={"estado": "afk", "desde": None, "ahora": "2026-11-16 10:00:00"})

    c = ClienteApi("http://servidor", "tok", transport=httpx.MockTransport(manejador), reintentos=0, dormir=lambda s: None)
    c.cambiar_estado("afk")
    c.cambiar_estado("afk", INACTIVIDAD)
    assert cuerpos == [{"estado": "afk"}, {"estado": "afk", "motivo": "inactividad"}]
