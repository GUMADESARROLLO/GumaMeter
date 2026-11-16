"""Medidor de uso de aplicaciones: qué se cuenta y qué no."""

from uso import MedidorUso


class Pantalla:
    """Simula lo que hay en primer plano y hace cuánto no se toca el teclado ni el mouse."""

    def __init__(self):
        self.actual = ("chrome.exe", "Google Chrome", 0.0)

    def __call__(self):
        if isinstance(self.actual, Exception):
            raise self.actual
        return self.actual


def medidor(**kw):
    pantalla = Pantalla()
    return MedidorUso(leer=pantalla, paso=5, umbral=300, **kw), pantalla


def test_acumula_segundos_por_programa():
    m, pantalla = medidor()
    for _ in range(6):
        m.muestrear()
    pantalla.actual = ("excel.exe", "Microsoft Excel", 2.0)
    for _ in range(3):
        m.muestrear()

    carga = m.tomar()
    assert carga == {
        "apps": [
            {"proceso": "chrome.exe", "nombre": "Google Chrome", "segundos": 30},
            {"proceso": "excel.exe", "nombre": "Microsoft Excel", "segundos": 15},
        ],
        "inactivo": 0,
    }
    assert m.tomar() is None  # tomar deja el medidor en cero


def test_mas_de_5_minutos_quieto_cuenta_como_sin_actividad():
    m, pantalla = medidor()
    pantalla.actual = ("chrome.exe", "Google Chrome", 299.0)
    m.muestrear()  # todavía cuenta para el programa
    pantalla.actual = ("chrome.exe", "Google Chrome", 300.0)
    m.muestrear()
    m.muestrear()
    assert m.tomar() == {"apps": [{"proceso": "chrome.exe", "nombre": "Google Chrome", "segundos": 5}], "inactivo": 10}


def test_sin_ventana_activa_no_se_cuenta_nada():
    m, pantalla = medidor()
    pantalla.actual = (None, None, 3.0)
    m.muestrear()
    assert m.tomar() is None


def test_un_fallo_al_leer_no_rompe_ni_cuenta():
    m, pantalla = medidor()
    pantalla.actual = OSError("acceso denegado")
    m.muestrear()
    assert m.tomar() is None


def test_tope_sin_conexion():
    m, _ = medidor(tope=20)
    for _ in range(10):
        m.muestrear()
    assert m.total() == 20


def test_devolver_reincorpora_un_envio_fallido():
    m, pantalla = medidor(tope=60)
    m.muestrear()
    carga = m.tomar()
    pantalla.actual = ("excel.exe", "Microsoft Excel", 0.0)
    m.muestrear()
    m.devolver(carga)
    assert m.total() == 10
    assert {a["proceso"]: a["segundos"] for a in m.tomar()["apps"]} == {"excel.exe": 5, "chrome.exe": 5}


def test_devolver_respeta_el_tope():
    m, _ = medidor(tope=10)
    m.devolver({"apps": [{"proceso": "a.exe", "nombre": "A", "segundos": 8}], "inactivo": 9})
    assert m.total() == 10


def test_lectura_real_de_windows_devuelve_solo_programa_y_tiempo():
    import sys

    from uso import lectura_windows

    proceso, nombre, quieto = lectura_windows()
    print("lectura real:", proceso, "|", nombre, "|", round(quieto, 1))
    assert quieto >= 0
    if sys.platform == "win32" and proceso:
        assert proceso == proceso.lower() and nombre
