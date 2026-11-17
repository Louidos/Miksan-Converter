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
    # Eine Zeile JSON; das Zeilenende markiert „Nachricht vollständig“
    verbindung.write(json.dumps({"pfade": pfade}).encode("utf-8") + b"\n")
    verbindung.flush()
    verbindung.waitForBytesWritten(WARTEN_MS)
    # Erst trennen, wenn das Fenster „ok“ gesagt hat – sonst gehen unter Windows (Named
    # Pipes) die Daten verloren, wenn das Fenster noch nicht gelesen hat.
    verbindung.waitForReadyRead(WARTEN_MS * 2)
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
            verbindung.disconnected.connect(lambda v=verbindung: self._lesen(v, ende=True))
            # Daten können schon da sein (z. B. unter Windows), bevor die Signale verbunden sind
            self._lesen(
                verbindung,
                ende=verbindung.state() == QLocalSocket.LocalSocketState.UnconnectedState,
            )

    def _lesen(self, verbindung: QLocalSocket, ende: bool = False) -> None:
        if verbindung not in self._puffer:
            return  # schon verarbeitet
        self._puffer[verbindung] += bytes(verbindung.readAll())
        if self._puffer[verbindung].endswith(b"\n") or ende:
            self._fertig(verbindung)

    @staticmethod
    def _loesen(verbindung: QLocalSocket) -> None:
        """Eigene Signal-Verbindungen trennen, bevor Qt die Verbindung freigibt (sonst ruft
        ``disconnected`` während des Aufräumens noch unseren Code auf)."""
        for signal in (verbindung.readyRead, verbindung.disconnected):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                pass

    def _fertig(self, verbindung: QLocalSocket) -> None:
        daten = self._puffer.pop(verbindung, b"")
        self._loesen(verbindung)
        if verbindung.state() == QLocalSocket.LocalSocketState.ConnectedState:
            verbindung.write(b"ok\n")
            verbindung.flush()
            verbindung.disconnectFromServer()
        verbindung.deleteLater()
        if not daten.strip():
            return
        try:
            pfade = json.loads(daten.decode("utf-8")).get("pfade", [])
        except (ValueError, AttributeError):
            return
        self.dateien.emit([str(p) for p in pfade if isinstance(p, str)])

    def schliessen(self) -> None:
        for verbindung in list(self._puffer):
            self._loesen(verbindung)
            verbindung.abort()
        self._puffer.clear()
        self.server.close()


def verbinden(fenster, instanz: Einzelinstanz, nach_vorne: Callable[[], None]) -> None:
    """Dateien aus weiteren Starts in das Fenster geben und es nach vorne holen."""

    def empfangen(pfade: list[str]) -> None:
        if pfade:
            fenster.dateien_von_aussen(pfade)
        nach_vorne()

    instanz.dateien.connect(empfangen)
