"""Instancia única por usuario de Windows.

La primera ejecución escucha en un canal local. La segunda solo se conecta a
ese canal y termina; para la primera, esa conexión es la orden de mostrar su menú.
"""

from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _nombre_canal() -> str:
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = "usuario"
    return f"GumaMeter-{usuario}"


class InstanciaUnica(QObject):
    mostrar_pedido = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._servidor: QLocalServer | None = None

    def avisar_a_la_primera(self) -> bool:
        """True si ya había una instancia (y con conectarse quedó avisada)."""
        enchufe = QLocalSocket()
        enchufe.connectToServer(_nombre_canal())
        if not enchufe.waitForConnected(400):
            return False
        enchufe.disconnectFromServer()
        return True

    def escuchar(self) -> bool:
        self._servidor = QLocalServer(self)
        self._servidor.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._servidor.newConnection.connect(self._al_conectar)
        if self._servidor.listen(_nombre_canal()):
            return True
        # Canal huérfano de un cierre abrupto: se limpia y se reintenta.
        QLocalServer.removeServer(_nombre_canal())
        return self._servidor.listen(_nombre_canal())

    def _al_conectar(self) -> None:
        while self._servidor and self._servidor.hasPendingConnections():
            enchufe = self._servidor.nextPendingConnection()
            enchufe.disconnected.connect(enchufe.deleteLater)
            enchufe.disconnectFromServer()
            self.mostrar_pedido.emit()
