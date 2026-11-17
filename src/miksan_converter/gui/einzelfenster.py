"""Nur ein Fenster: ein zweiter Start (z. B. über das Explorer-Rechtsklick-Menü) gibt seine
Dateien an das laufende Fenster weiter und beendet sich sofort.

Verbindung über ``QLocalServer``/``QLocalSocket`` (unter Windows eine Named Pipe, sonst ein
lokaler Socket); der Name enthält den Benutzernamen, damit sich Benutzer nicht stören.
"""

from __future__ import annotations

import getpass
import json
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

WARTEN_MS = 1500


def standard_name() -> str:
    try:
        benutzer = getpass.getuser()
    except Exception:  # ohne Benutzernamen (selten)
        benutzer = "benutzer"
    sauber = "".join(z for z in benutzer if z.isalnum()) or "benutzer"
    return f"miksan-converter-{sauber}"


def an_laufendes_senden(pfade: list[str], name: str | None = None) -> bool:
    """Gibt die Dateien an ein laufendes Fenster weiter. ``True`` = es läuft schon eines."""
    verbindung = QLocalSocket()
    verbindung.connectToServer(name or standard_name())
    if not verbindung.waitForConnected(WARTEN_MS):
        return False
    verbindung.write(json.dumps({"pfade": pfade}).encode("utf-8"))
    verbindung.flush()
    verbindung.waitForBytesWritten(WARTEN_MS)
    verbindung.disconnectFromServer()
    if verbindung.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        verbindung.waitForDisconnected(WARTEN_MS)
    return True


class Einzelinstanz(QObject):
    """Server im ersten Fenster; meldet Dateien aus weiteren Starts über ``dateien``."""

    dateien = Signal(list)

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name or standard_name()
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._neue_verbindung)
        self._puffer: dict[QLocalSocket, bytes] = {}

    def starten(self) -> bool:
        """Startet den Server; ``False``, wenn der Name schon belegt ist."""
        return self.server.listen(self.name)

    def aufraeumen_und_starten(self) -> bool:
        """Räumt einen verwaisten Socket (z. B. nach einem Absturz) auf und startet neu."""
        QLocalServer.removeServer(self.name)
        return self.server.listen(self.name)

    def _neue_verbindung(self) -> None:
        while self.server.hasPendingConnections():
            verbindung = self.server.nextPendingConnection()
            self._puffer[verbindung] = b""
            verbindung.readyRead.connect(lambda v=verbindung: self._lesen(v))
            verbindung.disconnected.connect(lambda v=verbindung: self._fertig(v))

    def _lesen(self, verbindung: QLocalSocket) -> None:
        self._puffer[verbindung] = self._puffer.get(verbindung, b"") + bytes(verbindung.readAll())

    def _fertig(self, verbindung: QLocalSocket) -> None:
        self._lesen(verbindung)
        daten = self._puffer.pop(verbindung, b"")
        verbindung.deleteLater()
        try:
            pfade = json.loads(daten.decode("utf-8")).get("pfade", [])
        except (ValueError, AttributeError):
            return
        self.dateien.emit([str(p) for p in pfade if isinstance(p, str)])

    def schliessen(self) -> None:
        self.server.close()


def verbinden(fenster, instanz: Einzelinstanz, nach_vorne: Callable[[], None]) -> None:
    """Dateien aus weiteren Starts in das Fenster geben und es nach vorne holen."""

    def empfangen(pfade: list[str]) -> None:
        if pfade:
            fenster.dateien_von_aussen(pfade)
        nach_vorne()

    instanz.dateien.connect(empfangen)
