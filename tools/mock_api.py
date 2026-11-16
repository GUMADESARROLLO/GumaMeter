"""Servidor simulado de la API SAC, para probar la app mientras la real no exista.

Implementa el mismo contrato (base ``/api/sac``). Solo usa la biblioteca estándar.

    python tools/mock_api.py                 # http://127.0.0.1:8765
    python tools/mock_api.py --puerto 9000 --sin-senal 30

En la app, pon en Configuración la dirección ``http://127.0.0.1:8765``.

Usuarios de prueba (contraseña ``1234``):

    SAC01, SAC02, SAC03   rol SAC, activos
    VENTAS01              no es SAC      -> 403
    SAC99                 SAC inactivo   -> 403

Mientras corre, escribe en esta consola para simular cambios hechos en el servidor:

    SAC03 lunch      pasa a SAC03 a Descanso (la app lo verá en el siguiente latido)
    caer             responde 503 a todo (simula el servidor caído); "subir" lo restablece
    ver              muestra el estado de todos
    uso              muestra el uso de aplicaciones recibido
"""

from __future__ import annotations

import argparse
import json
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MANAGUA = timezone(timedelta(hours=-6))
ESTADOS = ("on", "afk", "lunch", "off")
MAX_INTENTOS = 5  # intentos de login por minuto y por usuario

USUARIOS = {
    "SAC01": {"id": 1, "nombre": "Mario Rivas", "clave": "1234", "sac": True, "activo": True},
    "SAC02": {"id": 2, "nombre": "Ana Morales", "clave": "1234", "sac": True, "activo": True},
    "SAC03": {"id": 3, "nombre": "Lucía Castro", "clave": "1234", "sac": True, "activo": True},
    "VENTAS01": {"id": 4, "nombre": "Pedro Solís", "clave": "1234", "sac": False, "activo": True},
    "SAC99": {"id": 5, "nombre": "Usuario Inactivo", "clave": "1234", "sac": True, "activo": False},
}


def ahora() -> str:
    return datetime.now(MANAGUA).strftime("%Y-%m-%d %H:%M:%S")


class Mundo:
    """Estado en memoria del servidor simulado."""

    def __init__(self, sin_senal: float):
        self.candado = threading.Lock()
        self.sin_senal = sin_senal
        self.tokens: dict[str, str] = {}  # token -> username (sesión única: uno por usuario)
        self.dispositivos: dict[str, str] = {}  # token -> dispositivo
        self.desplazados: set[str] = set()  # tokens que dejaron de servir por entrar en otro equipo
        self.estados: dict[str, dict] = {}  # username -> {estado, desde, visto}
        self.intentos: dict[str, list[float]] = {}
        self.caido = False
        self.uso: dict[str, dict[str, int]] = {}  # username -> {proceso: segundos}

    def fijar(self, username: str, estado: str) -> dict:
        actual = self.estados.get(username)
        if not actual or actual["estado"] != estado:
            actual = {"estado": estado, "desde": ahora(), "visto": time.monotonic()}
            self.estados[username] = actual
        return actual

    def vigente(self, username: str) -> dict:
        actual = self.estados.get(username) or self.fijar(username, "off")
        # Sin señal de vida durante demasiado tiempo: pasa a Desconectado.
        if actual["estado"] != "off" and time.monotonic() - actual["visto"] > self.sin_senal:
            actual = self.fijar(username, "off")
        return actual

    def respuesta(self, username: str) -> dict:
        actual = self.vigente(username)
        return {"estado": actual["estado"], "desde": actual["desde"], "ahora": ahora()}


class Manejador(BaseHTTPRequestHandler):
    mundo: Mundo
    server_version = "MockSAC/1.0"

    # -- utilidades --------------------------------------------------------

    def _json(self, codigo: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        if not largo:
            return {}
        try:
            datos = json.loads(self.rfile.read(largo))
        except ValueError:
            return {}
        return datos if isinstance(datos, dict) else {}

    def _usuario(self) -> str | None:
        """Username del token, o None tras responder 401/403."""
        cabecera = self.headers.get("Authorization", "")
        token = cabecera[7:] if cabecera.startswith("Bearer ") else ""
        username = self.mundo.tokens.get(token)
        if not username:
            if token in self.mundo.desplazados:
                self._json(401, {"mensaje": "Tu sesión se cerró porque este usuario inició sesión en otro equipo."})
            else:
                self._json(401, {"mensaje": "Tu sesión no es válida o venció. Vuelve a iniciar sesión."})
            return None
        u = USUARIOS[username]
        if not u["sac"] or not u["activo"]:
            self._json(403, {"mensaje": "Tu usuario no tiene acceso a SAC Estados."})
            return None
        return username

    def log_message(self, formato: str, *args) -> None:
        print(f"[{ahora()[11:]}] {formato % args}")

    # -- rutas -------------------------------------------------------------

    def do_GET(self) -> None:
        self._atender("GET")

    def do_POST(self) -> None:
        self._atender("POST")

    def _atender(self, metodo: str) -> None:
        cuerpo = self._cuerpo()
        ruta = self.path.split("?")[0].rstrip("/")
        m = self.mundo
        with m.candado:
            if m.caido:
                return self._json(503, {"mensaje": "Servidor en mantenimiento."})
            if not ruta.endswith(("/api/sac/login", "/api/sac/estado", "/api/sac/latido", "/api/sac/logout", "/api/sac/uso")):
                return self._json(404, {"mensaje": "Ruta no encontrada."})
            accion = ruta.rsplit("/", 1)[1]

            if (metodo, accion) == ("POST", "login"):
                return self._login(cuerpo)
            if (metodo, accion) not in (("GET", "estado"), ("POST", "estado"), ("POST", "latido"), ("POST", "logout"), ("POST", "uso")):
                return self._json(405, {"mensaje": "Método no permitido."})

            username = self._usuario()
            if not username:
                return None
            if accion == "logout":
                token = self.headers["Authorization"][7:]
                m.tokens.pop(token, None)
                m.fijar(username, "off")
                return self._json(200, {"ok": True})
            if accion == "uso":
                apps, inactivo = cuerpo.get("apps"), cuerpo.get("inactivo")
                valido = isinstance(apps, list) and isinstance(inactivo, int) and inactivo >= 0 and all(
                    isinstance(a, dict) and isinstance(a.get("proceso"), str) and a["proceso"]
                    and isinstance(a.get("segundos"), int) and a["segundos"] > 0 for a in apps
                )
                if not valido or inactivo + sum(a["segundos"] for a in apps) > 600:
                    return self._json(422, {"mensaje": "El reporte de uso no es válido."})
                acumulado = m.uso.setdefault(username, {})
                for a in apps:
                    acumulado[a["proceso"].lower()] = acumulado.get(a["proceso"].lower(), 0) + a["segundos"]
                if inactivo:
                    acumulado["(inactivo)"] = acumulado.get("(inactivo)", 0) + inactivo
                return self._json(200, {"ok": True})
            if accion == "latido":
                m.vigente(username)["visto"] = time.monotonic()
            elif metodo == "POST":  # POST /estado
                nuevo = cuerpo.get("estado")
                if nuevo not in ESTADOS:
                    return self._json(422, {"mensaje": "El estado no es válido."})
                motivo = cuerpo.get("motivo")
                if motivo not in (None, "inactividad", "regreso"):
                    return self._json(422, {"mensaje": "El motivo no es válido."})
                m.fijar(username, nuevo)["visto"] = time.monotonic()
                if motivo:
                    print(f"   {username}: {nuevo} ({motivo})")
            return self._json(200, m.respuesta(username))

    def _login(self, cuerpo: dict) -> None:
        m = self.mundo
        username = str(cuerpo.get("username", "")).strip().upper()
        clave = str(cuerpo.get("password", ""))
        dispositivo = str(cuerpo.get("dispositivo", "")).strip()

        recientes = [t for t in m.intentos.get(username, []) if time.monotonic() - t < 60]
        if len(recientes) >= MAX_INTENTOS:
            return self._json(429, {"mensaje": "Demasiados intentos. Espera un minuto y vuelve a intentar."})

        u = USUARIOS.get(username)
        if not u or u["clave"] != clave or not dispositivo:
            m.intentos[username] = recientes + [time.monotonic()]
            return self._json(401, {"mensaje": "Usuario o contraseña incorrectos."})
        if not u["sac"]:
            return self._json(403, {"mensaje": "Esta aplicación es solo para usuarios de SAC."})
        if not u["activo"]:
            return self._json(403, {"mensaje": "Tu usuario está inactivo. Habla con tu supervisor."})

        m.intentos.pop(username, None)
        # Sesión única: entrar en un equipo cierra la sesión de la app en cualquier otro
        for viejo in [t for t, quien in m.tokens.items() if quien == username]:
            if m.dispositivos.pop(viejo, None) != dispositivo:
                m.desplazados.add(viejo)
            del m.tokens[viejo]
        token = secrets.token_urlsafe(32)
        m.tokens[token] = username
        m.dispositivos[token] = dispositivo
        m.vigente(username)["visto"] = time.monotonic()
        return self._json(
            200,
            {
                "token": token,
                "usuario": {"id": u["id"], "nombre": u["nombre"], "username": username},
                **m.respuesta(username),
            },
        )


def crear_servidor(host: str = "127.0.0.1", puerto: int = 8765, sin_senal: float = 180.0) -> ThreadingHTTPServer:
    """Crea el servidor sin arrancarlo (las pruebas lo usan con ``puerto=0``)."""
    manejador = type("ManejadorSAC", (Manejador,), {"mundo": Mundo(sin_senal)})
    return ThreadingHTTPServer((host, puerto), manejador)


def _consola(mundo: Mundo) -> None:
    while True:
        try:
            linea = input().strip()
        except EOFError:
            return
        partes = linea.split()
        with mundo.candado:
            if linea == "caer":
                mundo.caido = True
                print("-> el servidor ahora responde 503")
            elif linea == "subir":
                mundo.caido = False
                print("-> el servidor volvió")
            elif linea == "ver":
                for username in USUARIOS:
                    print(f"   {username:9} {mundo.vigente(username)['estado']}")
            elif linea == "uso":
                for username, apps in mundo.uso.items():
                    print(f"   {username}: " + ", ".join(f"{p} {s}s" for p, s in sorted(apps.items(), key=lambda x: -x[1])))
            elif len(partes) == 2 and partes[0].upper() in USUARIOS and partes[1] in ESTADOS:
                mundo.fijar(partes[0].upper(), partes[1])["visto"] = time.monotonic()
                print(f"-> {partes[0].upper()} pasó a {partes[1]}")
            elif linea:
                print("Comandos: <USUARIO> <on|afk|lunch|off> · caer · subir · ver")


def main() -> None:
    ap = argparse.ArgumentParser(description="Servidor simulado de la API SAC")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-senal", type=float, default=180.0, help="segundos sin latido antes de pasar a Desconectado")
    args = ap.parse_args()

    servidor = crear_servidor(args.host, args.puerto, args.sin_senal)
    print(f"API SAC simulada en http://{args.host}:{args.puerto}  (base /api/sac)")
    print("Usuarios: SAC01, SAC02, SAC03 (contraseña 1234) · VENTAS01 y SAC99 dan 403")
    print("Comandos: <USUARIO> <on|afk|lunch|off> · caer · subir · ver · Ctrl+C para salir")
    threading.Thread(target=_consola, args=(servidor.RequestHandlerClass.mundo,), daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
