"""Blau-Weiss-Design: alle Farben, Masse, das Stylesheet und die Icons an einer Stelle.

Andere Module setzen keine eigenen Farben, sondern nur Rollen als Qt-Eigenschaft, z. B.
``knopf.setProperty("rolle", "primaer")`` oder ``label.setProperty("rolle", "hinweis")``.
Das Stylesheet unten gibt jeder Rolle ihr Aussehen.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

# --- Farben -------------------------------------------------------------------------------

HINTERGRUND = "#FFFFFF"
FLAECHE = "#F4F8FD"  # Karten, Seitenleiste, Eingabefelder im Ruhezustand
FLAECHE_HOVER = "#E8F0FB"
RAHMEN = "#D6E2F0"
RAHMEN_STARK = "#B4C6DD"
AKZENT = "#1E6FE0"
AKZENT_HOVER = "#185BC0"
AKZENT_GEDRUECKT = "#134A9E"
AKZENT_HELL = "#DCE9FB"  # Auswahl in Listen, Seitenleiste aktiv
TEXT = "#0F1B2D"
NEBENTEXT = "#5B6B82"
TEXT_AUS = "#9AA8BA"  # ausgegraut
FEHLER = "#C62828"
ERFOLG = "#1B7F4B"
WARNUNG = "#9A5B00"
AUF_AKZENT = "#FFFFFF"  # Text auf gefülltem Blau
SCHACHBRETT_HELL = "#FFFFFF"
SCHACHBRETT_DUNKEL = "#E3E9F2"

# --- Masse ----------------------------------------------------------------------------------

RASTER = 8  # alle Abstände sind Vielfache davon
RADIUS = 8
RADIUS_KLEIN = 4
SCHRIFT_PT = 10  # Grundgrösse (Windows/Linux); macOS behält die Systemgrösse
SCHRIFT_TITEL_PT = 16
SCHRIFT_UNTERTITEL_PT = 12
ICON = 18  # Icons in Knöpfen und Listen
ICON_GROSS = 32  # Icons auf den Karten der Startseite
SEITENLEISTE_BREITE = 208
SCROLLBALKEN = 10

ICON_ORDNER = Path(__file__).with_name("icons")


def abstand(n: float = 1) -> int:
    """Abstand im 8-px-Raster, z. B. ``abstand(2) == 16``."""
    return round(RASTER * n)


# --- Kontrast (WCAG) ------------------------------------------------------------------------


def _helligkeit(farbe: str) -> float:
    werte = [int(farbe.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [w / 12.92 if w <= 0.03928 else ((w + 0.055) / 1.055) ** 2.4 for w in werte]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def kontrast(vorne: str, hinten: str) -> float:
    """Kontrastverhältnis nach WCAG 2 (1 bis 21)."""
    a, b = sorted((_helligkeit(vorne), _helligkeit(hinten)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# --- Stylesheet -----------------------------------------------------------------------------


def stylesheet() -> str:
    """Das zentrale Qt-Stylesheet (QSS) für die ganze App."""
    r, rk, a = RADIUS, RADIUS_KLEIN, abstand
    return f"""
QWidget {{
    color: {TEXT};
    selection-background-color: {AKZENT};
    selection-color: {AUF_AKZENT};
}}
QMainWindow, QDialog, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {HINTERGRUND};
}}
QWidget:disabled {{ color: {TEXT_AUS}; }}

/* Texte mit Rolle */
QLabel[rolle="titel"] {{ font-size: {SCHRIFT_TITEL_PT}pt; font-weight: 600; }}
QLabel[rolle="untertitel"] {{ font-size: {SCHRIFT_UNTERTITEL_PT}pt; font-weight: 600; }}
QLabel[rolle="bereich"] {{
    color: {NEBENTEXT}; font-weight: 600; padding: {a(1)}px {a(1.5)}px {a(0.5)}px;
}}
QLabel[rolle="hinweis"] {{ color: {NEBENTEXT}; }}
QLabel[rolle="fehler"] {{ color: {FEHLER}; }}
QLabel[rolle="erfolg"] {{ color: {ERFOLG}; }}
QLabel[rolle="warnung"] {{ color: {WARNUNG}; }}

/* Karten und Flächen */
QFrame[rolle="karte"], QGroupBox {{
    background: {FLAECHE};
    border: 1px solid {RAHMEN};
    border-radius: {r}px;
}}
QFrame[rolle="karte"]:hover {{ border-color: {AKZENT}; }}
QFrame[rolle="flaeche"] {{ background: {FLAECHE}; border: none; }}
QFrame[rolle="leiste"] {{ background: {HINTERGRUND}; border-top: 1px solid {RAHMEN}; }}
QFrame[rolle="ablage"] {{
    background: {FLAECHE};
    border: 2px dashed {RAHMEN_STARK};
    border-radius: {r}px;
}}
QFrame[rolle="ablage"][aktiv="true"] {{ border-color: {AKZENT}; background: {AKZENT_HELL}; }}
QGroupBox {{ margin-top: {a(2.5)}px; padding: {a(2)}px {a(1.5)}px {a(1.5)}px; }}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: {a(1)}px; padding: 0 {a(0.5)}px; color: {TEXT}; font-weight: 600;
}}

/* Knöpfe: Standard weiss mit blauem Rahmen, Hauptknopf gefüllt blau */
QPushButton, QToolButton {{
    background: {HINTERGRUND};
    color: {AKZENT};
    border: 1px solid {AKZENT};
    border-radius: {r}px;
    padding: {a(0.75)}px {a(2)}px;
    min-height: {a(2.5)}px;
}}
QPushButton:hover, QToolButton:hover {{ background: {FLAECHE_HOVER}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {AKZENT_HELL}; }}
QPushButton:disabled, QToolButton:disabled {{
    color: {TEXT_AUS}; border-color: {RAHMEN}; background: {HINTERGRUND};
}}
QPushButton:focus, QToolButton:focus {{ outline: none; border: 2px solid {AKZENT_GEDRUECKT}; }}
QPushButton[rolle="primaer"] {{
    background: {AKZENT}; color: {AUF_AKZENT}; border: 1px solid {AKZENT}; font-weight: 600;
}}
QPushButton[rolle="primaer"]:hover {{ background: {AKZENT_HOVER}; border-color: {AKZENT_HOVER}; }}
QPushButton[rolle="primaer"]:pressed {{ background: {AKZENT_GEDRUECKT}; }}
QPushButton[rolle="primaer"]:focus {{ border: 2px solid {TEXT}; }}
QPushButton[rolle="primaer"]:disabled {{
    background: {RAHMEN}; border-color: {RAHMEN}; color: {AUF_AKZENT};
}}
QPushButton[rolle="flach"], QToolButton[rolle="flach"] {{
    border: 1px solid transparent; background: transparent; padding: {a(0.5)}px;
    min-height: 0;
}}
QPushButton[rolle="flach"]:hover, QToolButton[rolle="flach"]:hover {{
    background: {FLAECHE_HOVER};
}}
QPushButton[rolle="flach"]:focus, QToolButton[rolle="flach"]:focus {{
    border: 2px solid {AKZENT};
}}

/* Seitenleiste */
QListWidget[rolle="seitenleiste"] {{
    background: {FLAECHE}; border: none; border-right: 1px solid {RAHMEN};
    padding: {a(1)}px; outline: none;
}}
QListWidget[rolle="seitenleiste"]::item {{
    border-radius: {r}px; padding: {a(1)}px {a(1)}px; margin: 1px 0; color: {TEXT};
}}
QListWidget[rolle="seitenleiste"]::item:hover {{ background: {FLAECHE_HOVER}; }}
QListWidget[rolle="seitenleiste"]::item:selected {{
    background: {AKZENT_HELL}; color: {AKZENT_GEDRUECKT}; font-weight: 600;
}}
QListWidget[rolle="seitenleiste"]::item:disabled {{ color: {TEXT_AUS}; background: transparent; }}

/* Eingabefelder und Auswahllisten */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit, QPlainTextEdit, QTextEdit {{
    background: {HINTERGRUND};
    border: 1px solid {RAHMEN_STARK};
    border-radius: {r}px;
    padding: {a(0.5)}px {a(1)}px;
    min-height: {a(2.5)}px;
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QTimeEdit:hover {{
    border-color: {AKZENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {AKZENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {FLAECHE}; border-color: {RAHMEN};
}}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{
    width: {a(2)}px; border: none; background: transparent;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow {{
    image: url({_icon_url("hoch")}); width: 12px; height: 12px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow {{
    image: url({_icon_url("aufklappen")}); width: 12px; height: 12px;
}}
QComboBox::drop-down {{ border: none; width: {a(3)}px; }}
QComboBox::down-arrow {{ image: url({_icon_url("aufklappen")}); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: {HINTERGRUND}; border: 1px solid {RAHMEN_STARK}; border-radius: {rk}px;
    padding: {a(0.5)}px; outline: none;
    selection-background-color: {AKZENT_HELL}; selection-color: {TEXT};
}}

/* Checkboxen und Radioknöpfe */
QCheckBox, QRadioButton {{ spacing: {a(1)}px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px; border: 1px solid {RAHMEN_STARK}; background: {HINTERGRUND};
}}
QCheckBox::indicator {{ border-radius: {rk}px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {AKZENT}; }}
QCheckBox::indicator:focus, QRadioButton::indicator:focus {{ border: 2px solid {AKZENT}; }}
QCheckBox::indicator:checked {{
    background: {AKZENT}; border-color: {AKZENT}; image: url({_icon_url("haken", AUF_AKZENT)});
}}
QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {AUF_AKZENT}, stop:0.35 {AUF_AKZENT}, stop:0.45 {AKZENT}, stop:1 {AKZENT});
    border-color: {AKZENT};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {FLAECHE}; border-color: {RAHMEN};
}}

/* Listen und Tabellen */
QListWidget, QListView, QTreeView, QTableView {{
    background: {HINTERGRUND};
    border: 1px solid {RAHMEN};
    border-radius: {r}px;
    outline: none;
    alternate-background-color: {FLAECHE};
}}
QListWidget::item, QListView::item, QTreeView::item {{ padding: {a(0.5)}px; }}
QListWidget::item:hover, QListView::item:hover, QTreeView::item:hover {{
    background: {FLAECHE_HOVER};
}}
QListWidget::item:selected, QListView::item:selected, QTreeView::item:selected {{
    background: {AKZENT_HELL}; color: {TEXT};
}}
QHeaderView::section {{
    background: {FLAECHE}; color: {NEBENTEXT}; border: none;
    border-bottom: 1px solid {RAHMEN}; padding: {a(0.5)}px {a(1)}px;
}}

/* Fortschrittsbalken */
QProgressBar {{
    background: {FLAECHE}; border: 1px solid {RAHMEN}; border-radius: {r}px;
    text-align: center; color: {TEXT}; min-height: {a(2.5)}px;
}}
QProgressBar::chunk {{ background: {AKZENT}; border-radius: {r - 1}px; }}

/* Schieberegler */
QSlider::groove:horizontal {{ height: 4px; background: {RAHMEN}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {AKZENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {HINTERGRUND}; border: 2px solid {AKZENT};
    width: 14px; height: 14px; margin: -7px 0; border-radius: 9px;
}}
QSlider::handle:horizontal:focus {{ border-color: {AKZENT_GEDRUECKT}; background: {AKZENT_HELL}; }}

/* Schmale Scrollbalken */
QScrollBar:vertical {{ background: transparent; width: {SCROLLBALKEN}px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: {SCROLLBALKEN}px; margin: 2px; }}
QScrollBar::handle {{ background: {RAHMEN_STARK}; border-radius: 3px; }}
QScrollBar::handle:vertical {{ min-height: {a(3)}px; }}
QScrollBar::handle:horizontal {{ min-width: {a(3)}px; }}
QScrollBar::handle:hover {{ background: {NEBENTEXT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Tooltips, Menüs, Trenner */
QToolTip {{
    background: {TEXT}; color: {AUF_AKZENT}; border: none;
    border-radius: {rk}px; padding: {a(0.5)}px {a(1)}px;
}}
QMenu {{ background: {HINTERGRUND}; border: 1px solid {RAHMEN}; padding: {a(0.5)}px; }}
QMenu::item {{ padding: {a(0.5)}px {a(2)}px; border-radius: {rk}px; }}
QMenu::item:selected {{ background: {AKZENT_HELL}; color: {TEXT}; }}
QSplitter::handle {{ background: {RAHMEN}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QMessageBox {{ background: {HINTERGRUND}; }}
"""


# --- Icons ----------------------------------------------------------------------------------


def icon_namen() -> list[str]:
    """Alle mitgelieferten Icons (Dateien ``icons/*.svg``)."""
    return sorted(pfad.stem for pfad in ICON_ORDNER.glob("*.svg"))


def svg_text(name: str, farbe: str = TEXT) -> str:
    """SVG-Quelltext eines Icons in der gewünschten Farbe."""
    pfad = ICON_ORDNER / f"{name}.svg"
    return pfad.read_text(encoding="utf-8").replace("currentColor", farbe)


@cache
def _icon_url(name: str, farbe: str = NEBENTEXT) -> str:
    """Farbiges Icon als Datei für ``url(...)`` im Stylesheet (Qt liest dort nur Dateien)."""
    import tempfile

    ordner = Path(tempfile.gettempdir()) / "miksan-converter-icons"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{name}-{farbe.lstrip('#').lower()}.svg"
    if not ziel.is_file() or ziel.read_text(encoding="utf-8") != svg_text(name, farbe):
        ziel.write_text(svg_text(name, farbe), encoding="utf-8")
    return ziel.as_posix()


@cache
def icon(name: str, farbe: str = TEXT):
    """Linien-Icon als ``QIcon``, gestochen scharf auch bei 125–200 % Skalierung."""
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg_text(name, farbe).encode("utf-8")))
    ergebnis = QIcon()
    for groesse in (16, 18, 20, 24, 32, 48, 64, 96, 128):
        bild = QPixmap(groesse, groesse)
        bild.fill(Qt.GlobalColor.transparent)
        maler = QPainter(bild)
        maler.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(maler, QRectF(0, 0, groesse, groesse))
        maler.end()
        ergebnis.addPixmap(bild)
    return ergebnis


def programm_icon_pfad() -> Path:
    return Path(__file__).with_name("miksan.png")


def programm_icon():
    """Programm-Icon aus dem Paket (falls vorhanden), sonst ein leeres Icon."""
    from PySide6.QtGui import QIcon

    pfad = programm_icon_pfad()
    return QIcon(str(pfad)) if pfad.is_file() else QIcon()


# --- Anwenden -------------------------------------------------------------------------------


def hohe_aufloesung_einrichten() -> None:
    """Vor dem Erzeugen der QApplication: Skalierung 125 %/150 % nicht auf 100 %/200 % runden."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )


def palette():
    """Farbpalette passend zum Stylesheet (für Stellen, die Qt selbst zeichnet)."""
    from PySide6.QtGui import QColor, QPalette

    p = QPalette()
    rollen = QPalette.ColorRole
    for rolle, farbe in (
        (rollen.Window, HINTERGRUND),
        (rollen.WindowText, TEXT),
        (rollen.Base, HINTERGRUND),
        (rollen.AlternateBase, FLAECHE),
        (rollen.Text, TEXT),
        (rollen.Button, HINTERGRUND),
        (rollen.ButtonText, AKZENT),
        (rollen.Highlight, AKZENT),
        (rollen.HighlightedText, AUF_AKZENT),
        (rollen.ToolTipBase, TEXT),
        (rollen.ToolTipText, AUF_AKZENT),
        (rollen.PlaceholderText, NEBENTEXT),
        (rollen.Link, AKZENT),
        (rollen.Light, HINTERGRUND),
        (rollen.Midlight, FLAECHE),
        (rollen.Mid, RAHMEN),
        (rollen.Dark, RAHMEN_STARK),
    ):
        p.setColor(rolle, QColor(farbe))
    for rolle in (rollen.WindowText, rollen.Text, rollen.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, rolle, QColor(TEXT_AUS))
    return p


def anwenden(app) -> None:
    """Fusion-Stil, Palette, Schrift und Stylesheet setzen – überall gleich (Win/macOS/Linux)."""
    app.setStyle("Fusion")
    app.setPalette(palette())
    schrift = app.font()
    if sys.platform != "darwin":  # macOS: Systemgrösse 13 pt entspricht dort 10 pt
        schrift.setPointSize(SCHRIFT_PT)
    app.setFont(schrift)
    app.setStyleSheet(stylesheet())
    app.setProperty("miksan_design", True)


def eigenschaft(widget, rolle: str):
    """Setzt die Rolle eines Widgets und frischt seinen Stil auf; gibt das Widget zurück."""
    widget.setProperty("rolle", rolle)
    stil = widget.style()
    stil.unpolish(widget)
    stil.polish(widget)
    return widget
