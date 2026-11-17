"""Zuschnitt mit der Maus: Rechteck aufziehen oder verschieben, optional mit festem Verhältnis.

Das Rechteck wird relativ zum Bild gespeichert (Anteile 0–1), damit es unabhängig von der
Anzeigegrösse und der echten Bildgrösse stimmt.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .. import design
from .vorschau import schachbrett


class ZuschnittAnsicht(QWidget):
    geaendert = Signal(tuple)  # (x, y, b, h) relativ

    def __init__(self) -> None:
        super().__init__()
        self.bild: QPixmap | None = None
        self.verhaeltnis: tuple[int, int] | None = None
        self.relativ = (0.0, 0.0, 1.0, 1.0)
        self._modus: str | None = None
        self._start = QPointF()
        self._start_relativ = self.relativ
        self._schachbrett = schachbrett()
        self.setMinimumHeight(design.abstand(20))
        self.setMouseTracking(True)
        self.setToolTip("Rechteck aufziehen; innen ziehen verschiebt den Ausschnitt")

    # --- Daten ----------------------------------------------------------------------------

    def bild_setzen(self, bild: QPixmap | None, relativ=None) -> None:
        self.bild = bild
        self.relativ = tuple(relativ) if relativ else self.mittig()
        self.update()

    def verhaeltnis_setzen(self, verhaeltnis: tuple[int, int] | None) -> None:
        self.verhaeltnis = verhaeltnis
        self.relativ = self.mittig()
        self.update()
        self.geaendert.emit(self.relativ)

    def mittig(self) -> tuple[float, float, float, float]:
        """Grösster mittiger Ausschnitt mit dem Verhältnis (relativ)."""
        if self.bild is None or self.verhaeltnis is None:
            return (0.0, 0.0, 1.0, 1.0)
        vb, vh = self.verhaeltnis
        breite, hoehe = self.bild.width(), self.bild.height()
        if breite * vh > hoehe * vb:
            anteil = (hoehe * vb / vh) / breite
            return ((1 - anteil) / 2, 0.0, anteil, 1.0)
        anteil = (breite * vh / vb) / hoehe
        return (0.0, (1 - anteil) / 2, 1.0, anteil)

    # --- Geometrie --------------------------------------------------------------------------

    def bild_rechteck(self) -> QRectF:
        if self.bild is None:
            return QRectF()
        rand = design.abstand(1)
        platz = QRectF(self.rect()).adjusted(rand, rand, -rand, -rand)
        massstab = min(platz.width() / self.bild.width(), platz.height() / self.bild.height())
        breite, hoehe = self.bild.width() * massstab, self.bild.height() * massstab
        return QRectF(
            platz.center().x() - breite / 2, platz.center().y() - hoehe / 2, breite, hoehe
        )

    def auswahl_rechteck(self) -> QRectF:
        ziel = self.bild_rechteck()
        x, y, b, h = self.relativ
        return QRectF(
            ziel.x() + x * ziel.width(),
            ziel.y() + y * ziel.height(),
            b * ziel.width(),
            h * ziel.height(),
        )

    def _relativ_aus(self, punkt: QPointF) -> QPointF:
        ziel = self.bild_rechteck()
        return QPointF(
            min(1.0, max(0.0, (punkt.x() - ziel.x()) / max(1.0, ziel.width()))),
            min(1.0, max(0.0, (punkt.y() - ziel.y()) / max(1.0, ziel.height()))),
        )

    def _aufziehen(self, a: QPointF, b: QPointF) -> None:
        x0, y0 = min(a.x(), b.x()), min(a.y(), b.y())
        breite, hoehe = abs(b.x() - a.x()), abs(b.y() - a.y())
        if self.verhaeltnis is not None and self.bild is not None:
            vb, vh = self.verhaeltnis
            # relative Masse in Pixel-Verhältnis umrechnen
            bild_v = self.bild.width() / self.bild.height()
            soll = (vb / vh) / bild_v  # relative Breite / relative Höhe
            if breite / max(hoehe, 1e-6) > soll:
                breite = hoehe * soll
            else:
                hoehe = breite / soll
            if b.x() < a.x():
                x0 = a.x() - breite
            if b.y() < a.y():
                y0 = a.y() - hoehe
        if breite > 0.01 and hoehe > 0.01:
            self.relativ = (x0, y0, breite, hoehe)

    # --- Maus -------------------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.button() != Qt.MouseButton.LeftButton or self.bild is None:
            return
        self._start = self._relativ_aus(event.position())
        self._start_relativ = self.relativ
        innen = self.auswahl_rechteck().contains(event.position())
        self._modus = "verschieben" if innen else "aufziehen"

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._modus is None:
            innen = self.auswahl_rechteck().contains(event.position())
            form = Qt.CursorShape.SizeAllCursor if innen else Qt.CursorShape.CrossCursor
            self.setCursor(form)
            return
        punkt = self._relativ_aus(event.position())
        if self._modus == "verschieben":
            x, y, b, h = self._start_relativ
            dx, dy = punkt.x() - self._start.x(), punkt.y() - self._start.y()
            self.relativ = (min(max(0.0, x + dx), 1 - b), min(max(0.0, y + dy), 1 - h), b, h)
        else:
            self._aufziehen(self._start, punkt)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._modus is not None:
            self._modus = None
            self.geaendert.emit(self.relativ)

    # --- Zeichnen ---------------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        maler = QPainter(self)
        maler.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        maler.fillRect(self.rect(), QColor(design.FLAECHE))
        if self.bild is None:
            maler.setPen(QColor(design.NEBENTEXT))
            maler.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Bild in der Liste wählen")
            return
        ziel = self.bild_rechteck()
        maler.fillRect(ziel, self._schachbrett)
        maler.drawPixmap(ziel, self.bild, QRectF(self.bild.rect()))
        auswahl = self.auswahl_rechteck()
        abdunkeln = QColor(design.TEXT)
        abdunkeln.setAlpha(140)
        for teil in (
            QRectF(ziel.left(), ziel.top(), ziel.width(), auswahl.top() - ziel.top()),
            QRectF(ziel.left(), auswahl.bottom(), ziel.width(), ziel.bottom() - auswahl.bottom()),
            QRectF(ziel.left(), auswahl.top(), auswahl.left() - ziel.left(), auswahl.height()),
            QRectF(
                auswahl.right(), auswahl.top(), ziel.right() - auswahl.right(), auswahl.height()
            ),
        ):
            maler.fillRect(teil, abdunkeln)
        drittel = QPen(QColor(design.AUF_AKZENT), 1, Qt.PenStyle.DashLine)
        maler.setPen(drittel)
        for i in (1, 2):
            x = auswahl.left() + auswahl.width() * i / 3
            y = auswahl.top() + auswahl.height() * i / 3
            maler.drawLine(QPointF(x, auswahl.top()), QPointF(x, auswahl.bottom()))
            maler.drawLine(QPointF(auswahl.left(), y), QPointF(auswahl.right(), y))
        maler.setPen(QPen(QColor(design.AKZENT), 2))
        maler.drawRect(auswahl)
