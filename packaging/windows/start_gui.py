"""Startskript für Miksan-Converter.exe (Oberfläche, ohne Konsolenfenster)."""

import sys

import _laufzeit  # noqa: F401 – Umgebung vor allen anderen Importen einrichten

from miksan_converter.gui import main

sys.exit(main())
