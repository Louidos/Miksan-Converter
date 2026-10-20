"""Erzeugt das Programm-Icon (miksan.ico für Windows, miksan.png für das Fenster).

Aufruf aus dem Repo-Ordner: ``uv run python packaging/windows/icon_erzeugen.py``
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ORDNER = Path(__file__).resolve().parent
ICO = ORDNER / "miksan.ico"
PNG = ORDNER.parent.parent / "src" / "miksan_converter" / "gui" / "miksan.png"
GROESSEN = (16, 20, 24, 32, 40, 48, 64, 128, 256)
S = 1024  # gezeichnet wird gross, danach verkleinert

OBEN = (37, 99, 235)  # Blau
UNTEN = (13, 148, 136)  # Petrol
WEISS = (255, 255, 255, 255)
SONNE = (251, 191, 36, 255)


def _verlauf() -> Image.Image:
    verlauf = Image.new("RGBA", (S, S))
    zeichnen = ImageDraw.Draw(verlauf)
    for y in range(S):
        t = y / (S - 1)
        farbe = tuple(round(a + (b - a) * t) for a, b in zip(OBEN, UNTEN, strict=True))
        zeichnen.line([(0, y), (S, y)], fill=(*farbe, 255))
    return verlauf


def zeichnen() -> Image.Image:
    maske = Image.new("L", (S, S), 0)
    ImageDraw.Draw(maske).rounded_rectangle([32, 32, S - 32, S - 32], radius=200, fill=255)
    bild = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bild.paste(_verlauf(), (0, 0), maske)

    d = ImageDraw.Draw(bild)
    # hinteres Bild (Umriss, leicht versetzt)
    d.rounded_rectangle([300, 190, 840, 610], radius=60, outline=WEISS, width=46)
    # vorderes Bild mit Berg und Sonne
    d.rounded_rectangle([184, 400, 724, 820], radius=60, fill=WEISS)
    d.ellipse([560, 460, 660, 560], fill=SONNE)
    d.polygon([(220, 790), (400, 560), (520, 700), (590, 630), (690, 790)], fill=(*UNTEN, 255))
    # Pfeil: umwandeln
    d.line([(150, 330), (250, 230)], fill=WEISS, width=46)
    d.polygon([(290, 190), (160, 215), (265, 320)], fill=WEISS)
    return bild


def main() -> None:
    gross = zeichnen()
    bilder = [gross.resize((g, g), Image.Resampling.LANCZOS) for g in GROESSEN]
    bilder[-1].save(ICO, sizes=[(g, g) for g in GROESSEN], append_images=bilder[:-1])
    bilder[-1].save(PNG)
    print(f"Geschrieben: {ICO}")
    print(f"Geschrieben: {PNG}")


if __name__ == "__main__":
    main()
