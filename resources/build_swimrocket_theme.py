"""Генерирует фирменную тему SwimRocket на основе исходной темы TalkTrack."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = (ROOT / "style.qss").read_text(encoding="utf-8")
palette = {
    "#1e1e2e": "#242841",  # основной фирменный синий
    "#181825": "#1B1E33",
    "#313244": "#353A59",
    "#45475a": "#484E70",
    "#585b70": "#62698B",
    "#cdd6f4": "#F7F8FC",
    "#a6adc8": "#B9BED3",
    "#89b4fa": "#F1642E",
    "#f38ba8": "#F1642E",
    "#eba0ac": "#FF7647",
    "#fab387": "#FDE676",
    "#f9e2af": "#FDE676",
    "#bac2de": "#FFEAA0",
    "#b4d0fb": "#FF8B62",
    "#a6e3a1": "#7DE2C3",
}
for old, new in palette.items():
    source = source.replace(old, new)

source += r"""

/* SwimRocket: фирменная шапка и статус серверной обработки */
QFrame#brandHeader {
    background-color: #1B1E33;
    border-bottom: 2px solid #F1642E;
}
QLabel#brandTitle {
    color: #FDE676;
    font-family: "BebasNeueCyrillic", "Arial Narrow", sans-serif;
    font-size: 27px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#brandSubtitle {
    color: #B9BED3;
    font-size: 11px;
}
QLabel#serverBadge {
    color: #FDE676;
    background-color: #353A59;
    border: 1px solid #F1642E;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#serverBadgeDetail {
    color: #B9BED3;
    font-size: 10px;
}
QLineEdit#meetingNameInput, QLineEdit#meetingParticipantsInput {
    background-color: #353A59;
    border: 1px solid #484E70;
    border-radius: 9px;
    padding: 9px 12px;
}
QLineEdit#meetingNameInput:focus, QLineEdit#meetingParticipantsInput:focus {
    border: 1px solid #F1642E;
}
QFrame#collapsibleHeader {
    background-color: #353A59;
    border-left: 3px solid #F1642E;
}
"""
(ROOT / "swimrocket-theme.qss").write_text(source, encoding="utf-8")
print(ROOT / "swimrocket-theme.qss")
