"""
Modern, high-performance QSS stylesheet system for SnipGlide Qt.
Inspired by WhatsApp Web Dark / Modern Fluent interfaces.
Hardware accelerated, crisp, with prominent input borders and high-contrast typography.
"""

def get_stylesheet(font_family: str = "Tajawal", base_font_size: int = 15, is_dark: bool = True) -> str:
    if is_dark:
        bg_main = "#0b141a"
        bg_sidebar = "#111b21"
        bg_card = "#182229"
        bg_card_hover = "#202c33"
        bg_input = "#202c33"
        bg_input_focus = "#2a3942"
        text_primary = "#f0f2f5"
        text_secondary = "#94a3b8"
        accent = "#25D366"
        accent_hover = "#1da851"
        border_color = "#2a3942"
        input_border = "#3b4a54"
        input_border_focus = "#25D366"
    else:
        bg_main = "#f0f2f5"
        bg_sidebar = "#ffffff"
        bg_card = "#ffffff"
        bg_card_hover = "#f5f6f6"
        bg_input = "#f7f8fa"
        bg_input_focus = "#ffffff"
        text_primary = "#111b21"
        text_secondary = "#64748b"
        accent = "#25D366"
        accent_hover = "#1da851"
        border_color = "#e2e8f0"
        input_border = "#cbd5e1"
        input_border_focus = "#25D366"

    return f"""
    *:not(#notepadTextEditor) {{
        font-family: "{font_family}", "Segoe UI", "Tahoma", sans-serif;
        font-size: {base_font_size}px;
        color: {text_primary};
        outline: none;
    }}

    QMainWindow, QWidget#centralWidget {{
        background-color: {bg_main};
    }}

    /* ─── Sidebar ─── */
    QFrame#sidebarFrame {{
        background-color: {bg_sidebar};
        border-right: 1.5px solid {border_color};
    }}

    QPushButton.navButton {{
        text-align: left;
        padding: 12px 18px;
        border-radius: 10px;
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
        color: #93c5fd;
        border-left: 4px solid #3b82f6;
        font-weight: bold;
    }}

    /* ─── Cards and Panels ─── */
    QFrame.cardFrame, QFrame#headerFrame {{
        background-color: {bg_card};
        border-radius: 14px;
        border: 1.5px solid {border_color};
    }}

    /* ─── Inputs & Editors (Highly Visible, High-Contrast Borders) ─── */
    QLineEdit {{
        background-color: {bg_input};
        color: {text_primary};
        border: 2px solid {input_border};
        border-radius: 10px;
        padding: 10px 14px;
        font-size: {base_font_size}px;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}

    QLineEdit:focus {{
        background-color: {bg_input_focus};
        border: 2px solid {input_border_focus};
    }}

    QLineEdit::placeholder {{
        color: #64748b;
        font-size: {base_font_size}px;
    }}

    QPlainTextEdit:not(#notepadTextEditor), QTextEdit {{
        background-color: {bg_input};
        color: {text_primary};
        border: 2px solid {input_border};
        border-radius: 10px;
        padding: 12px 14px;
        font-size: {base_font_size}px;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}

    QPlainTextEdit:not(#notepadTextEditor):focus, QTextEdit:focus {{
        background-color: {bg_input_focus};
        border: 2px solid {input_border_focus};
    }}

    /* ─── Buttons ─── */
    QPushButton.primaryBtn {{
        background-color: {accent};
        color: #ffffff;
        font-weight: bold;
        padding: 10px 22px;
        border-radius: 10px;
        border: none;
        font-size: {base_font_size}px;
    }}

    QPushButton.primaryBtn:hover {{
        background-color: {accent_hover};
    }}

    QPushButton.secondaryBtn {{
        background-color: {bg_card};
        color: {text_primary};
        padding: 8px 18px;
        border-radius: 10px;
        border: 1.5px solid {border_color};
        font-size: {base_font_size}px;
    }}

    QPushButton.secondaryBtn:hover {{
        background-color: {bg_card_hover};
        border-color: {input_border};
    }}

    QPushButton.dangerBtn {{
        background-color: #dc2626;
        color: #ffffff;
        font-weight: bold;
        padding: 8px 18px;
        border-radius: 10px;
        border: none;
        font-size: {base_font_size}px;
    }}

    QPushButton.dangerBtn:hover {{
        background-color: #b91c1c;
    }}

    /* ─── Section Pills ─── */
    QPushButton.sectionPill {{
        background-color: {bg_card};
        color: {text_primary};
        border-radius: 18px;
        padding: 6px 18px;
        font-size: {base_font_size - 1}px;
        border: 1.5px solid {border_color};
    }}

    QPushButton.sectionPill:hover {{
        background-color: {bg_card_hover};
        border-color: {input_border};
    }}

    QPushButton.sectionPill:checked, QPushButton.sectionPill[active="true"] {{
        background-color: {accent};
        color: #ffffff;
        font-weight: bold;
        border: none;
    }}

    /* ─── ComboBox (Prominent Dropdown) ─── */
    QComboBox {{
        background-color: {bg_input};
        border: 2px solid {input_border};
        border-radius: 10px;
        padding: 8px 14px;
        color: {text_primary};
        font-size: {base_font_size}px;
        min-height: 24px;
    }}

    QComboBox:focus {{
        border: 2px solid {input_border_focus};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {bg_card};
        border: 2px solid {input_border};
        selection-background-color: {accent};
        selection-color: #ffffff;
        color: {text_primary};
        border-radius: 8px;
        padding: 6px;
    }}

    /* ─── Lists ─── */
    QListWidget {{
        background-color: {bg_input};
        border: 2px solid {input_border};
        border-radius: 12px;
        padding: 6px;
    }}

    QListWidget::item {{
        background-color: {bg_card};
        color: {text_primary};
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 4px;
        border: 1px solid {border_color};
    }}

    QListWidget::item:hover {{
        background-color: {bg_card_hover};
        border-color: {input_border};
    }}

    QListWidget::item:selected {{
        background-color: #172554;
        color: #93c5fd;
        font-weight: bold;
        border: 1.5px solid #3b82f6;
    }}

    /* ─── Scrollbars ─── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {input_border};
        min-height: 30px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {text_secondary};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
        height: 0px;
    }}
    """
