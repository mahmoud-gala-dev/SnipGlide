"""
Modern, high-performance QSS stylesheet system for SnipGlide Qt.
Inspired by WhatsApp Web Dark / Modern Fluent interfaces.
Hardware accelerated, crisp, with native font rendering and zero Tkinter overhead.
"""

def get_stylesheet(font_family: str = "Tajawal", base_font_size: int = 14, is_dark: bool = True) -> str:
    if is_dark:
        bg_main = "#111b21"
        bg_sidebar = "#0c1317"
        bg_card = "#1f2c34"
        bg_card_hover = "#2a3942"
        bg_input = "#2a3942"
        bg_scroll = "#0b141a"
        text_primary = "#e9edef"
        text_secondary = "#8696a0"
        accent = "#25D366"
        accent_hover = "#1da851"
        border_color = "#222d34"
        bubble_bg = "#005c4b"
        bubble_starred = "#064e3b"
    else:
        bg_main = "#f0f2f5"
        bg_sidebar = "#ffffff"
        bg_card = "#ffffff"
        bg_card_hover = "#f5f6f6"
        bg_input = "#f0f2f5"
        bg_scroll = "#efeae2"
        text_primary = "#111b21"
        text_secondary = "#667781"
        accent = "#25D366"
        accent_hover = "#1da851"
        border_color = "#e9edef"
        bubble_bg = "#d9fdd3"
        bubble_starred = "#fef08a"

    return f"""
    * {{
        font-family: "{font_family}", "Segoe UI", "Tahoma", sans-serif;
        font-size: {base_font_size}px;
        color: {text_primary};
        outline: none;
    }}

    QMainWindow, QWidget#centralWidget {{
        background-color: {bg_main};
    }}

    /* Sidebar */
    QFrame#sidebarFrame {{
        background-color: {bg_sidebar};
        border-right: 1px solid {border_color};
    }}

    QPushButton.navButton {{
        text-align: left;
        padding: 10px 16px;
        border-radius: 8px;
        background-color: transparent;
        color: {text_secondary};
        font-weight: bold;
        font-size: {base_font_size}px;
        border: none;
    }}

    QPushButton.navButton:hover {{
        background-color: {bg_card_hover};
        color: {text_primary};
    }}

    QPushButton.navButton:checked, QPushButton.navButton[active="true"] {{
        background-color: #172554;
        color: #60a5fa;
        border-left: 3px solid #3b82f6;
    }}

    /* Cards and Containers */
    QFrame.cardFrame {{
        background-color: {bg_card};
        border-radius: 12px;
        border: 1px solid {border_color};
    }}

    /* Inputs and text edits */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {bg_input};
        color: {text_primary};
        border-radius: 8px;
        padding: 8px 12px;
        border: 1px solid transparent;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {accent};
    }}

    /* Buttons */
    QPushButton.primaryBtn {{
        background-color: {accent};
        color: #ffffff;
        font-weight: bold;
        padding: 8px 18px;
        border-radius: 8px;
        border: none;
    }}

    QPushButton.primaryBtn:hover {{
        background-color: {accent_hover};
    }}

    QPushButton.secondaryBtn {{
        background-color: {bg_card};
        color: {text_primary};
        padding: 6px 14px;
        border-radius: 8px;
        border: 1px solid {border_color};
    }}

    QPushButton.secondaryBtn:hover {{
        background-color: {bg_card_hover};
    }}

    QPushButton.dangerBtn {{
        background-color: #dc2626;
        color: #ffffff;
        font-weight: bold;
        padding: 6px 14px;
        border-radius: 8px;
        border: none;
    }}

    QPushButton.dangerBtn:hover {{
        background-color: #b91c1c;
    }}

    /* Section Pills */
    QPushButton.sectionPill {{
        background-color: {bg_card};
        color: {text_primary};
        border-radius: 15px;
        padding: 6px 16px;
        font-size: {base_font_size - 1}px;
        border: 1px solid {border_color};
    }}

    QPushButton.sectionPill:hover {{
        background-color: {bg_card_hover};
    }}

    QPushButton.sectionPill:checked, QPushButton.sectionPill[active="true"] {{
        background-color: {accent};
        color: #ffffff;
        font-weight: bold;
        border: none;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {bg_card_hover};
        min-height: 25px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {text_secondary};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background: {bg_card_hover};
        min-width: 25px;
        border-radius: 3px;
    }}

    /* ComboBox */
    QComboBox {{
        background-color: {bg_card};
        border: 1px solid {border_color};
        border-radius: 8px;
        padding: 6px 12px;
        color: {text_primary};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {bg_card};
        border: 1px solid {border_color};
        selection-background-color: {accent};
        selection-color: #ffffff;
        color: {text_primary};
        border-radius: 6px;
        padding: 4px;
    }}

    /* Toast overlay */
    QLabel#toastLabel {{
        background-color: #16a34a;
        color: #ffffff;
        font-weight: bold;
        border-radius: 8px;
        padding: 10px 20px;
    }}
    """
