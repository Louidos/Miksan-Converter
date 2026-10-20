"""Startskript für miksan.exe (Kommandozeile)."""

import sys

import _laufzeit  # noqa: F401 – Umgebung vor allen anderen Importen einrichten

from miksan_converter.cli import main

sys.exit(main())
