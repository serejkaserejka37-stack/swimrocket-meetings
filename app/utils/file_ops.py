"""Кроссплатформенное открытие файлов и папок."""
import os
import subprocess
import sys


def open_path(path):
    path = str(path)
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
