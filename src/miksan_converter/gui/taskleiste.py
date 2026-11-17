"""Fortschritt im Taskleisten-Symbol (Windows 7 und neuer, ITaskbarList3 über ctypes).

Auf anderen Systemen oder wenn etwas nicht klappt, tun alle Methoden still nichts – der
Fortschritt im Fenster bleibt davon unberührt.
"""

from __future__ import annotations

import ctypes
import sys
import uuid

# ITaskbarList3::SetProgressState
KEIN = 0
UNBESTIMMT = 0x1
NORMAL = 0x2
FEHLER = 0x4

_CLSID = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
_IID = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"
# Plätze in der vtable: IUnknown (0-2), ITaskbarList (3-7), ITaskbarList2 (8), ITaskbarList3 (9-)
_HR_INIT, _SET_VALUE, _SET_STATE = 3, 9, 10


class _Guid(ctypes.Structure):
    _fields_ = [("bytes", ctypes.c_byte * 16)]

    @classmethod
    def aus(cls, text: str) -> _Guid:
        guid = cls()
        ctypes.memmove(guid.bytes, uuid.UUID(text).bytes_le, 16)
        return guid


class Taskleiste:
    def __init__(self) -> None:
        self._zeiger = None
        if sys.platform != "win32":
            return
        try:
            ole32 = ctypes.windll.ole32
            ole32.CoInitialize(None)
            zeiger = ctypes.c_void_p()
            ergebnis = ole32.CoCreateInstance(
                ctypes.byref(_Guid.aus(_CLSID)),
                None,
                1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(_Guid.aus(_IID)),
                ctypes.byref(zeiger),
            )
            if ergebnis == 0 and zeiger.value:
                self._zeiger = zeiger
                self._aufrufen(_HR_INIT, [])
        except Exception:  # ohne COM: kein Taskleisten-Fortschritt
            self._zeiger = None

    @property
    def aktiv(self) -> bool:
        return self._zeiger is not None

    def _aufrufen(self, platz: int, argumente: list, typen: tuple = ()) -> None:
        if self._zeiger is None:
            return
        tabelle = ctypes.cast(self._zeiger, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        funktion = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *typen)(
            tabelle.contents[platz]
        )
        funktion(self._zeiger, *argumente)

    def zustand(self, fenster: int, zustand: int) -> None:
        try:
            self._aufrufen(_SET_STATE, [fenster, zustand], (ctypes.c_void_p, ctypes.c_int))
        except Exception:
            pass

    def wert(self, fenster: int, fertig: int, gesamt: int) -> None:
        try:
            self._aufrufen(
                _SET_VALUE,
                [fenster, max(0, fertig), max(1, gesamt)],
                (ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_ulonglong),
            )
        except Exception:
            pass
