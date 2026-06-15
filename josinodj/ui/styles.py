DARK_STYLE = """
* {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: #e0e0e0;
}

QMainWindow, QWidget {
    background-color: #111111;
}

QSplitter::handle {
    background-color: #1f1f1f;
}
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical   { height: 2px; }

/* ── Tables ─────────────────────────────────────────── */
QTableView {
    background-color: #141414;
    gridline-color: #1e1e1e;
    border: none;
    selection-background-color: #1c2f4a;
    selection-color: #ffffff;
    alternate-background-color: #161616;
}
QTableView::item { padding: 4px 6px; border: none; }
QTableView::item:hover { background-color: #202030; }

QHeaderView { background-color: #111111; border: none; }
QHeaderView::section {
    background-color: #111111;
    color: #555555;
    border: none;
    border-bottom: 1px solid #1f1f1f;
    border-right: 1px solid #2a2a2a;
    padding: 5px 8px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QHeaderView::section:last { border-right: none; }
QHeaderView::section:hover { color: #aaaaaa; background-color: #171717; }

/* ── Tree ────────────────────────────────────────────── */
QTreeView {
    background-color: #121212;
    border: none;
    color: #cccccc;
    alternate-background-color: #141414;
}
QTreeView::item { padding: 3px 4px; }
QTreeView::item:hover { background-color: #1c1c1c; }
QTreeView::item:selected { background-color: #1c2f4a; color: #ffffff; }

/* ── Buttons ─────────────────────────────────────────── */
QPushButton {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 5px 12px;
}
QPushButton:hover { background-color: #2a2a2a; border-color: #3a3a3a; }
QPushButton:pressed { background-color: #111111; }
QPushButton:checked { background-color: #1a2a40; border-color: #3a5a80; color: #5ab4ff; }

QPushButton#playBtn {
    background-color: #5a50e0;
    border: none;
    border-radius: 22px;
    min-width: 44px; max-width: 44px;
    min-height: 44px; max-height: 44px;
    font-size: 18px;
    color: white;
}
QPushButton#playBtn:hover { background-color: #6a60f0; }
QPushButton#playBtn:pressed { background-color: #4a40c0; }

QPushButton#autoBtn:checked {
    background-color: #1a4030;
    border-color: #2a7055;
    color: #3dcf9a;
}

QPushButton#cueBtn {
    background-color: #2a1f3a;
    border-color: #4a3a6a;
    color: #bb86fc;
    font-size: 11px;
    padding: 4px 10px;
}
QPushButton#cueBtn:hover { background-color: #3a2f4a; }
QPushButton#cueBtn:checked { background-color: #3a1f5a; border-color: #bb86fc; }

/* ── Sliders ─────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background-color: #2a2a2a;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background-color: #5a50e0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background-color: #7a70ff;
    width: 12px; height: 12px;
    border-radius: 6px;
    margin: -4px 0;
}
QSlider::handle:horizontal:hover { background-color: #9a90ff; }

QSlider#progressSlider::sub-page:horizontal { background-color: #00ccff; }
QSlider#progressSlider::handle:horizontal { background-color: #00ccff; }
QSlider#crossfadeSlider::sub-page:horizontal { background-color: #ff6b6b; }
QSlider#crossfadeSlider::handle:horizontal { background-color: #ff6b6b; }
QSlider#cueVolSlider::sub-page:horizontal { background-color: #bb86fc; }
QSlider#cueVolSlider::handle:horizontal { background-color: #bb86fc; }

/* ── Input fields ────────────────────────────────────── */
QLineEdit {
    background-color: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 5px 10px;
    color: #e0e0e0;
}
QLineEdit:focus { border-color: #5a50e0; }

QComboBox {
    background-color: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 5px 10px;
    color: #e0e0e0;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background-color: #1a1a1a;
    border: 1px solid #333333;
    selection-background-color: #2a3a5a;
    color: #e0e0e0;
}

QDoubleSpinBox, QSpinBox {
    background-color: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e0;
}

/* ── Scrollbars ──────────────────────────────────────── */
QScrollBar:vertical {
    background: #111111;
    width: 12px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2e2e3e;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: #4a4a6a; }
QScrollBar::handle:vertical:pressed { background: #6060aa; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #111111;
    height: 7px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background: #2a2a2a;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Player bar ──────────────────────────────────────── */
QWidget#playerBar {
    background-color: #0d0d0d;
    border-top: 2px solid #2a2060;
}

/* ── Library panel ───────────────────────────────────── */
QWidget#libraryPanel {
    background-color: #0f0f0f;
    border-right: 1px solid #1a1a1a;
}

/* ── Playlist toolbar ────────────────────────────────── */
QWidget#playlistToolbar {
    background-color: #111111;
    border-bottom: 1px solid #1a1a1a;
}

/* ── Labels ──────────────────────────────────────────── */
QLabel#nowTitle  { font-size: 14px; font-weight: 600; color: #ffffff; }
QLabel#nowArtist { font-size: 12px; color: #888888; }
QLabel#timeLabel { font-family: Consolas, monospace; font-size: 12px; color: #aaaaaa; }
QLabel#bpmKey    { font-size: 11px; color: #7a70ff; font-weight: 600; }
QLabel#sectionHdr {
    font-size: 10px; color: #444444; font-weight: bold;
    text-transform: uppercase; letter-spacing: 2px;
    padding: 4px 8px;
}

/* ── Menus ───────────────────────────────────────────── */
QMenu {
    background-color: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item { padding: 6px 18px; border-radius: 3px; }
QMenu::item:selected { background-color: #2a3a5a; }
QMenu::separator { height: 1px; background-color: #2a2a2a; margin: 3px 0; }

/* ── Misc ────────────────────────────────────────────── */
QStatusBar { background-color: #0a0a0a; color: #444444; font-size: 11px; }
QGroupBox {
    border: 1px solid #222222;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 6px;
    color: #555555;
    font-size: 11px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #cccccc; spacing: 8px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #333333;
    border-radius: 3px;
    background-color: #1a1a1a;
}
QCheckBox::indicator:checked { background-color: #5a50e0; border-color: #5a50e0; }
QToolTip {
    background-color: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #333333;
    padding: 4px 8px;
    border-radius: 3px;
}
QDialog { background-color: #141414; }
QTabWidget::pane { border: 1px solid #222222; background-color: #111111; }
QTabBar::tab {
    background-color: #141414;
    color: #666666;
    padding: 6px 14px;
    border: 1px solid #1f1f1f;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected { background-color: #111111; color: #e0e0e0; }
QTabBar::tab:hover { color: #aaaaaa; }
"""
