"""Заменяет старые тёмные inline-цвета TalkTrack на светлую палитру SwimRocket."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent / "app"
PALETTE = {
    "#1e1e2e": "#FFFFFF",
    "#181825": "#F8FAFC",
    "#313244": "#E4EAF3",
    "#45475a": "#D0D5DD",
    "#585b70": "#98A2B3",
    "#cdd6f4": "#242841",
    "#a6adc8": "#667085",
    "#89b4fa": "#F1642E",
    "#f38ba8": "#F1642E",
    "#f9e2af": "#F1642E",
    "#fde676": "#F1642E",
    "#fab387": "#FDE676",
    "#a6e3a1": "#34C759",
    "#b4d0fb": "#FF8B62",
    "#bac2de": "#FFEAA0",
    "#eba0ac": "#FF7542",
}
for path in ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in PALETTE.items():
        updated = re.sub(re.escape(old), new, updated, flags=re.I)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print(path.relative_to(ROOT.parent))
