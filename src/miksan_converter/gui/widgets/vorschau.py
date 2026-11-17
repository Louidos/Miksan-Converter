"""Vorschau mit Vorher/Nachher-Schieber, Zoom (Mausrad) und Verschieben (Ziehen).

Die Berechnung (``vorschaubild.vorschau_berechnen``) läuft verzögert im Thread-Pool; ältere
Ergebnisse werden verworfen, wenn inzwischen etwas geändert wurde.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import design
from .miniaturen import qimage_aus_pil

VERZOEGERUNG_MS = 300
_GRIFF = 8  # Pixel um die Linie, in denen Ziehen den Schieber bewegt


def schachbrett(kante: int = 8) -> QBrush:
    """Muster für transparente Stellen."""
    kachel = QPixmap(kante * 2, kante * 2)
    kachel.fill(QColor(design.SCHACHBRETT_HELL))
    maler = QPainter(kachel)
    dunkel = QColor(design.SCHACHBRETT_DUNKEL)
    maler.fillRect(0, 0, kante, kante, dunkel)
    maler.fillRect(kante, kante, kante, kante, dunkel)
    maler.end()
    return QBrush(kachel)


class VorherNachher(QWidget):
    """Zeigt links vom Schieber das Original, rechts das Ergebnis."""

    def __init__(self) -> None:
        super().__init__()
        self.vorher: QPixmap | None = None
        self.nachher: QPixmap | None = None
        self.teilung = 0.5  # Anteil der Breite, an dem die Linie steht
        self.zoom = 1.0
        self.versatz = QPointF(0, 0)
        self._ziehen: str | None = None  # "linie" oder "bild"
        self._start = QPointF()
        self._schachbrett = schachbrett()
        self.setMinimumHeight(design.abstand(20))
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Linie ziehen: vergleichen · Mausrad: zoomen · Doppelklick: zurücksetzen")

    def bilder_setzen(self, vorher: QPixmap | None, nachher: QPixmap | None) -> None:
        self.vorher, self.nachher = vorher, nachher
        self.update()

    def zuruecksetzen(self) -> None:
        self.zoom, self.versatz = 1.0, QPointF(0, 0)
        self.update()

    def bild_rechteck(self) -> QRectF:
        """Wo das Bild gezeichnet wird (eingepasst, dann gezoomt und verschoben)."""
        bild = self.vorher or self.nachher
        if bild is None:
            return QRectF()
        rand = design.abstand(1)
        verfuegbar = QRectF(self.rect()).adjusted(rand, rand, -rand, -rand)
        breite, hoehe = bild.width(), bild.height()
        massstab = min(verfuegbar.width() / breite, verfuegbar.height() / hoehe) * self.zoom
        groesse = QPointF(breite * massstab, hoehe * massstab)
        mitte = verfuegbar.center() + self.versatz
        return QRectF(mitte - groesse / 2, mitte + groesse / 2)

    def linie_x(self) -> float:
        return self.width() * self.teilung

    def paintEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        maler = QPainter(self)
        maler.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        maler.fillRect(self.rect(), QColor(design.FLAECHE))
        ziel = self.bild_rechteck()
        if ziel.isNull():
            maler.setPen(QColor(design.NEBENTEXT))
            maler.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Vorschau")
            return
        maler.fillRect(ziel, self._schachbrett)
        x = self.linie_x()
        for bild, links in ((self.vorher, True), (self.nachher, False)):
            if bild is None:
                continue
            maler.save()
            breite = self.width()
            maler.setClipRect(
                QRectF(0, 0, x, self.height()) if links else QRectF(x, 0, breite, self.height())
            )
            maler.drawPixmap(ziel, bild, QRectF(bild.rect()))
            maler.restore()
        maler.setPen(QPen(QColor(design.AUF_AKZENT), 3))
        maler.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        maler.setPen(QPen(QColor(design.AKZENT), 1))
        maler.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        maler.setBrush(QColor(design.AKZENT))
        maler.drawEllipse(QPointF(x, self.height() / 2), 7, 7)

    def mousePressEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.button() != Qt.MouseButton.LeftButton:
            return
        nahe = abs(event.position().x() - self.linie_x()) <= _GRIFF
        self._ziehen = "linie" if nahe or self.zoom == 1.0 else "bild"
        self._start = event.position() - self.versatz
        if self._ziehen == "linie":
            self._linie_setzen(event.position().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._ziehen == "linie":
            self._linie_setzen(event.position().x())
        elif self._ziehen == "bild":
            self.versatz = event.position() - self._start
            self.update()
        else:
            nahe = abs(event.position().x() - self.linie_x()) <= _GRIFF
            form = (
                Qt.CursorShape.SplitHCursor
                if nahe or self.zoom == 1.0
                else Qt.CursorShape.OpenHandCursor
            )
            self.setCursor(form)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self._ziehen = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.zuruecksetzen()

    def wheelEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        schritte = event.angleDelta().y() / 120
        if not schritte:
            return
        alt = self.zoom
        self.zoom = min(16.0, max(1.0, self.zoom * (1.25**schritte)))
        # Punkt unter der Maus bleibt stehen
        mitte = QRectF(self.rect()).center() + self.versatz
        self.versatz += (event.position() - mitte) * (1 - self.zoom / alt)
        if self.zoom == 1.0:
            self.versatz = QPointF(0, 0)
        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        schritt = {Qt.Key.Key_Left: -0.05, Qt.Key.Key_Right: 0.05}.get(event.key())
        if schritt is None:
            super().keyPressEvent(event)
            return
        self.teilung = min(1.0, max(0.0, self.teilung + schritt))
        self.update()

    def _linie_setzen(self, x: float) -> None:
        self.teilung = min(1.0, max(0.0, x / max(1, self.width())))
        self.update()


class _Bote(QObject):
    fertig = Signal(int, object, str)  # Nummer, Vorschau | None, Fehlertext


class _Rechnung(QRunnable):
    def __init__(self, nummer: int, rechnen: Callable[[], object], bote: _Bote) -> None:
        super().__init__()
        self.nummer, self.rechnen, self.bote = nummer, rechnen, bote

    def run(self) -> None:
        try:
            ergebnis = self.rechnen()
        except Exception as fehler:  # Vorschau darf nie das Fenster stören
            self.bote.fertig.emit(self.nummer, None, str(fehler))
        else:
            self.bote.fertig.emit(self.nummer, ergebnis, "")


class VorschauBereich(QWidget):
    """Vorher/Nachher-Ansicht mit Beschriftung; rechnet verzögert im Hintergrund."""

    berechnet = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.rechnen: Callable[[], object] | None = None
        self.letzte = None  # letzte berechnete Vorschau
        self._nummer = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._bote = _Bote()
        self._bote.fertig.connect(self._fertig)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(VERZOEGERUNG_MS)
        self._timer.timeout.connect(self._jetzt_rechnen)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, design.abstand(1), 0, 0)
        layout.setSpacing(design.abstand(0.5))
        kopf = QHBoxLayout()
        kopf.addWidget(design.eigenschaft(QLabel("Vorher"), "hinweis"))
        kopf.addStretch(1)
        self.titel = design.eigenschaft(QLabel("Vorschau"), "untertitel")
        kopf.addWidget(self.titel)
        kopf.addStretch(1)
        kopf.addWidget(design.eigenschaft(QLabel("Nachher"), "hinweis"))
        layout.addLayout(kopf)
        self.ansicht = VorherNachher()
        layout.addWidget(self.ansicht, 1)
        self.info = design.eigenschaft(QLabel(""), "hinweis")
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info)

    def anstossen(self, rechnen: Callable[[], object] | None) -> None:
        """Neue Berechnung planen (ersetzt eine noch nicht gestartete)."""
        self.rechnen = rechnen
        self._nummer += 1
        if rechnen is None:
            self.letzte = None
            self.ansicht.bilder_setzen(None, None)
            self.info.setText("")
            return
        self.info.setText("Vorschau wird berechnet …")
        self._timer.start()

    def _jetzt_rechnen(self) -> None:
        if self.rechnen is not None:
            self._pool.start(_Rechnung(self._nummer, self.rechnen, self._bote))

    def warten(self, ms: int = 10_000) -> bool:
        return self._pool.waitForDone(ms)

    def _fertig(self, nummer: int, vorschau, fehler: str) -> None:
        if nummer != self._nummer:
            return  # veraltet: inzwischen wurde etwas geändert
        if vorschau is None:
            self.letzte = None
            self.ansicht.bilder_setzen(None, None)
            self.info.setText(fehler)
            self.berechnet.emit()
            return
        self.letzte = vorschau
        self.ansicht.bilder_setzen(
            QPixmap.fromImage(qimage_aus_pil(vorschau.vorher)),
            QPixmap.fromImage(qimage_aus_pil(vorschau.nachher)),
        )
        self.info.setText(vorschau.hinweis or vorschau.text())
        self.berechnet.emit()
