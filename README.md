# SAC Estados

App de bandeja de Windows para el equipo de Servicio al Cliente (SAC) de Unimark S.A.
Sirve para una sola cosa: marcar el estado de trabajo (**En línea, AFK, Descanso, Desconectado**)
sin abrir el navegador. La app habla con la API del sistema SAC (Laravel), que valida al
usuario y registra cada cambio.

- Windows 10/11. Un solo archivo: `SAC-Estados.exe`.
- Python 3.11+, PySide6 (Qt), httpx, keyring y PyInstaller.

## Compilar

Requisitos: Windows, PowerShell y Python 3.11 o superior (o [uv](https://docs.astral.sh/uv/), que lo descarga solo).

```powershell
.\build.ps1              # crea .venv, instala, corre las pruebas y compila
.\build.ps1 -SinPruebas  # igual, sin pytest
```

El resultado queda en `dist\SAC-Estados.exe` (unos 40 MB). El script se detiene en el primer paso que falle.

Si PowerShell bloquea el script: `powershell -ExecutionPolicy Bypass -File .\build.ps1`.

## Probar sin la API real

La API real está en el proyecto Laravel SAC (`routes/api.php`, `SacApiController`, tabla
`tbl_sac_token`). Para probar la app sin tocar datos reales hay un servidor simulado que cumple
el mismo contrato:

```powershell
.\.venv\Scripts\python.exe tools\mock_api.py          # http://127.0.0.1:8765
.\.venv\Scripts\python.exe src\main.py                # la app, desde el código
```

En la app, abre **Configuración** y pon `http://127.0.0.1:8765`. Usuarios de prueba (contraseña `1234`):

| Usuario | Resultado |
|---|---|
| `SAC01`, `SAC02`, `SAC03` | entran |
| `VENTAS01` | 403: no es SAC |
| `SAC99` | 403: inactivo |

Cinco contraseñas malas seguidas dan 429 durante un minuto. En la consola del servidor simulado se puede escribir:

- `SAC03 lunch`: cambia el estado "desde el servidor"; la app lo refleja en el siguiente latido.
- `caer` / `subir`: simula el servidor caído y su regreso.
- `ver`: muestra el estado de todos.
- `uso`: muestra el uso de aplicaciones recibido.
- `--sin-senal 30` al arrancarlo acorta a 30 s la regla de "3 minutos sin señal".

Pruebas automáticas: `.\.venv\Scripts\python.exe -m pytest`

## Configurar la URL del servidor

La dirección se escribe **sin** `/api/sac`; la app lo agrega. Por defecto es `http://sac.umk.local`.

- **Desde la app:** clic en el ícono de la bandeja → **Configuración** (también hay un enlace en la ventana de inicio de sesión).
- **A mano o por script**, antes del primer uso: crear `%APPDATA%\SAC Estados\config.json`:

  ```json
  {
    "servidor": "http://servidor/SAC/public",
    "iniciar_con_windows": true
  }
  ```

El valor por defecto está en `src/settings.py` (`SERVIDOR_POR_DEFECTO`). Conviene poner ahí la
dirección real antes de compilar, para que nadie tenga que configurarla.

Si se cambia el servidor con una sesión abierta, la app cierra esa sesión y pide entrar de nuevo.

## Instalar en cada máquina

1. Copiar `SAC-Estados.exe` a una carpeta fija del equipo, por ejemplo `C:\SAC\SAC-Estados.exe`. No necesita instalador ni permisos de administrador.
2. Abrirlo e iniciar sesión con el usuario y la contraseña del sistema SAC. Solo entran usuarios con rol SAC.
3. Listo. Queda junto al reloj y **arranca solo con Windows** (clave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, valor `SAC Estados`). Se puede apagar con el interruptor "Iniciar con Windows" del menú.

Notas:

- Si Windows esconde el ícono, arrastrarlo desde la flecha `^` de la bandeja hasta la barra para dejarlo siempre visible.
- Si el `.exe` se mueve de carpeta, basta abrirlo una vez desde la carpeta nueva: corrige la ruta de inicio.
- El `.exe` no está firmado: SmartScreen puede avisar la primera vez ("Más información" → "Ejecutar de todas formas").
- Abrirlo dos veces no crea dos copias: la segunda solo muestra el menú de la primera.
- Para actualizar: salir de la app, reemplazar el `.exe` y abrirlo.
- Para desinstalar: apagar "Iniciar con Windows", salir y borrar el `.exe` y la carpeta `%APPDATA%\SAC Estados`.

## Cómo se usa

Clic (izquierdo o derecho) en el ícono → se abre el menú con el nombre del usuario y los cuatro estados.
El punto de color del ícono y el texto al pasar el mouse ("SAC Estados · En línea") muestran el estado vigente.

| Estado | Significado |
|---|---|
| En línea | Atendiendo pedidos |
| AFK | Ausente un momento |
| Descanso | Pausa programada |
| Desconectado | Fuera de turno |

**El ícono solo cambia cuando el servidor confirma.** Si el cambio no se pudo guardar, el estado
queda como estaba y aparece el aviso "No se pudo guardar el estado. Revisa la conexión."

Iniciar sesión **no** cambia el estado: la app muestra el que devuelve el servidor y el usuario elige.

## Qué pasa en cada caso

| Situación | Qué hace la app | Qué pasa con el estado |
|---|---|---|
| **Cerrar sesión** (menú) | Llama al logout, borra el token guardado y vuelve a la ventana de inicio de sesión. | El servidor pasa al usuario a **Desconectado** de inmediato y revoca el token. |
| **Salir** de la app (menú → Salir) | Pide confirmación y cierra el proceso. No cambia el estado ni cierra la sesión. | Sigue igual hasta que el servidor nota la falta de señal (3 minutos) y lo pasa a Desconectado. Al abrir la app de nuevo no pide contraseña. |
| **Apagar o suspender la máquina** | Nada: deja de enviar señal. | Igual que salir: Desconectado a los 3 minutos. Al volver, la app muestra lo que diga el servidor; el usuario marca "En línea" cuando retome. |
| **Sin conexión** | Ícono en gris con "Sin conexión"; reintenta cada 15 s. Sin confirmación del servidor el estado no cambia. | Si el corte pasa de 3 minutos, el servidor lo pasa a Desconectado y la app lo muestra al reconectar. |
| **Iniciar sesión en otra PC** | La app es de sesión única: la PC anterior vuelve a la ventana de inicio de sesión con el aviso "Tu sesión se cerró porque este usuario inició sesión en otro equipo." (en su siguiente latido, como mucho un minuto). | Se conserva; lo sigue manteniendo la PC nueva. |
| **Token vencido o revocado (401)** | Borra el token y vuelve a la ventana de inicio de sesión con un aviso. | Lo decide el servidor. |
| **Usuario desactivado o sin rol SAC (403)** | Igual que el 401, mostrando el mensaje del servidor. | Lo decide el servidor. |
| **Cerrar sesión sin conexión** | Borra el token local igual. | El servidor lo pasa a Desconectado por falta de señal; el token queda sin revocar hasta que venza. |

La señal de vida (latido) sale cada **60 segundos**. Su respuesta trae el estado vigente, así que un
cambio hecho en el servidor (por ejemplo, desde el sistema web) aparece en el ícono en menos de un minuto.
Al abrir el menú también se consulta el estado, para verlo al día.

## Cambios automáticos por inactividad

La app revisa cada 5 segundos cuánto tiempo lleva el equipo sin teclado ni mouse:

| Situación | Qué hace la app |
|---|---|
| **En línea** y 7 minutos sin actividad | Pasa a **AFK** y lo avisa. |
| Ese AFK automático y vuelve la actividad | Regresa sola a **En línea**. |
| **En línea o AFK** y 25 minutos sin actividad | Pasa a **Desconectado** y lo avisa. La sesión de la app sigue abierta. |
| Vuelve la actividad tras esa desconexión | Sigue en Desconectado y recuerda marcar **En línea** a mano. |

- Un **AFK elegido a mano** no vuelve solo a En línea, pero sí pasa a Desconectado a los 25 minutos.
- **Descanso** y **Desconectado** no se tocan.
- Con el menú abierto no se hace ningún cambio automático.
- El cambio sigue la regla de siempre: solo vale cuando el servidor lo confirma. Si falla, se reintenta a los 30 segundos.
- El servidor guarda el motivo, y la Bitácora de Equipo SAC lo muestra como "Inactividad" o "Regreso automático".
- Solo se detecta teclado y mouse: una llamada telefónica larga sin tocar el equipo cuenta como inactividad.

Los umbrales están en `src/inactividad.py` (`UMBRAL_AFK`, `UMBRAL_OFF`).

## Uso de aplicaciones

Mientras la persona tiene la sesión iniciada, **en cualquier estado** (En línea, AFK, Descanso o
Desconectado), la app anota cada 5 segundos qué programa está en primer
plano y lo envía al servidor junto con el latido. Con eso se arma la pestaña **Aplicaciones** de
Equipo SAC en el sistema web (tiempo por aplicación, por persona y tiempo sin actividad).

- **Qué se registra:** el nombre del programa (por ejemplo `chrome.exe` / "Google Chrome") y los segundos.
- **Qué no se registra:** títulos de ventana, páginas visitadas, teclas ni capturas de pantalla.
- **Sin actividad:** más de 5 minutos sin teclado ni mouse. Ese tiempo no se le suma a ningún programa.
- **Cuándo no mide:** sin sesión iniciada o sin conexión con el servidor.
- **Es visible:** el menú de la app lo dice siempre, al pie.
- **Sin conexión:** guarda hasta 9 minutos y los envía al reconectar.

Los umbrales están en `src/uso.py` (`PASO`, `UMBRAL_INACTIVO`, `TOPE`).

## Dónde se guarda cada cosa

| Dato | Lugar |
|---|---|
| Token de sesión | Administrador de credenciales de Windows → Credenciales de Windows → `SAC Estados`. Nunca en texto plano. |
| URL del servidor e "Iniciar con Windows" | `%APPDATA%\SAC Estados\config.json` |
| Inicio con Windows | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |

La contraseña no se guarda en ningún lado.

## Contrato de la API

Base: `{servidor}/api/sac`. Todo en JSON. Las rutas protegidas llevan `Authorization: Bearer {token}`.
Horas en `"AAAA-MM-DD HH:MM:SS"`, hora de Managua (UTC-6). Estados: `on`, `afk`, `lunch`, `off`.

| Método y ruta | Cuerpo | Respuesta 200 |
|---|---|---|
| `POST /login` | `{ "username", "password", "dispositivo" }` | `{ "token", "usuario": { "id", "nombre", "username" }, "estado", "desde", "ahora" }` |
| `GET /estado` | — | `{ "estado", "desde", "ahora" }` |
| `POST /estado` | `{ "estado", "motivo"? }` (`motivo`: `inactividad` o `regreso`, solo en cambios automáticos) | `{ "estado", "desde", "ahora" }` |
| `POST /latido` | — | `{ "estado", "desde", "ahora" }` |
| `POST /logout` | — | `{ "ok": true }` |
| `POST /uso` | `{ "apps": [{ "proceso", "nombre", "segundos" }], "inactivo" }` | `{ "ok": true }` |

Errores: **401** credenciales o token inválidos · **403** no es SAC o está inactivo · **422** estado no válido · **429** demasiados intentos.
Si la respuesta de error trae el campo `mensaje`, la app muestra ese texto; si no, usa uno propio.
`dispositivo` es el nombre del equipo (`COMPUTERNAME`).

Los errores de red, los tiempos agotados y las respuestas 502/503/504 se reintentan dos veces antes de darse por "sin conexión". Los 4xx no se reintentan.

## Estructura

```
src/
  main.py             arranque, hilo de trabajo y conexión entre las piezas
  api.py              cliente HTTP de la API (sin Qt)
  estado.py           lógica del estado: solo cambia si el servidor confirma (sin Qt)
  inactividad.py      cambios automáticos a AFK y Desconectado por inactividad
  uso.py              medidor de uso de aplicaciones (programa en primer plano e inactividad)
  tray.py             ícono de bandeja y menú propio
  login_window.py     ventana de inicio de sesión
  widgets.py          punto de estado, interruptor, campo y diálogos
  settings.py         config.json y token en el Administrador de credenciales
  theme.py            paleta clara y oscura, fuentes, hoja de estilos e íconos
  single_instance.py  instancia única
  run_at_startup.py   inicio con Windows
assets/
  fonts/              Archivo y Barlow Condensed (licencia OFL, incluida)
  images/             logotipos copiados de public/images del sistema web
  icon.ico            generado por tools/make_icon.py
tools/
  mock_api.py         servidor simulado
  make_icon.py        favicon-20.png -> icon.ico (16, 24, 32, 48, 256)
tests/                pytest: cliente de la API, lógica del estado y servidor simulado
SAC-Estados.spec      receta de PyInstaller
build.ps1             compilación completa
```

## Diseño

Sigue al sistema web SAC: fuentes Archivo (textos) y Barlow Condensed (horas), paleta azul rey,
modo claro y oscuro según el tema de Windows, y los colores de estado validados para daltonismo
(`src/theme.py`; no cambiarlos). El isotipo de la bandeja se elige según el color de la barra de
tareas, que puede ser oscura aunque las apps estén en modo claro.

## Referencia

La organización en módulos (cliente HTTP aparte, instancia única, inicio con Windows y script de
build que se detiene ante errores) sigue la idea general de apps de bandeja con PySide6 + httpx +
PyInstaller como [Clawdmeter](https://github.com/weltern/Clawdmeter). No se copió código de ese proyecto.
