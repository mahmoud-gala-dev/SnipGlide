from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea
)
from snipglide.database.snippet_repo import get_statistics

class DashboardQt(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        title = QLabel("لوحة الإحصائيات (Performance Dashboard)")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e9edef;")
        layout.addWidget(title)

        # Stats Cards Row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)

        self.snippets_card = self._create_card("إجمالي الاختصارات (Snippets)", "0", "#16a34a")
        self.groups_card = self._create_card("المجموعات (Groups)", "0", "#2563eb")
        self.expansions_card = self._create_card("مرات التوسيع (Expansions)", "0", "#f59e0b")

        cards_layout.addWidget(self.snippets_card)
        cards_layout.addWidget(self.groups_card)
        cards_layout.addWidget(self.expansions_card)
        layout.addLayout(cards_layout)

        # Most Used List Container
        most_used_frame = QFrame()
        most_used_frame.setStyleSheet("background-color: #1f2c34; border-radius: 12px; padding: 15px;")
        mu_layout = QVBoxLayout(most_used_frame)
        
        mu_title = QLabel("الأكثر استخداماً (Most Used Snippets)")
        mu_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e9edef;")
        mu_layout.addWidget(mu_title)

        self.mu_container = QWidget()
        self.mu_list_layout = QVBoxLayout(self.mu_container)
        self.mu_list_layout.setSpacing(8)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setWidget(self.mu_container)
        mu_layout.addWidget(scroll)

        layout.addWidget(most_used_frame, stretch=1)
        self.refresh_stats()

    def _create_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(f"background-color: #1f2c34; border-radius: 12px; border-left: 5px solid {color}; padding: 12px;")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(10, 8, 10, 8)
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 12px; color: #8696a0; font-weight: bold;")
        
        v_lbl = QLabel(value)
        v_lbl.setStyleSheet("font-size: 26px; font-weight: bold; color: #e9edef;")
        
        c_layout.addWidget(t_lbl)
        c_layout.addWidget(v_lbl)
        card.value_label = v_lbl
        return card

    def refresh_stats(self):
        try:
            stats = get_statistics()
            self.snippets_card.value_label.setText(str(stats["total_snippets"]))
            self.groups_card.value_label.setText(str(stats["total_groups"]))
            self.expansions_card.value_label.setText(str(stats["total_expansions"]))

            while self.mu_list_layout.count():
                item = self.mu_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            most_used = stats.get("most_used", [])
            if not most_used:
                no_lbl = QLabel("لا توجد إحصائيات مسجلة بعد.")
                no_lbl.setStyleSheet("color: #8696a0; font-size: 13px;")
                self.mu_list_layout.addWidget(no_lbl)
            else:
                for item in most_used:
                    row = QFrame()
                    row.setStyleSheet("background-color: #111b21; border-radius: 8px; padding: 10px;")
                    r_layout = QHBoxLayout(row)
                    r_layout.setContentsMargins(12, 6, 12, 6)
                    
                    sc_lbl = QLabel(item["shortcut"])
                    sc_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #e9edef;")
                    
                    cnt_lbl = QLabel(f"{item['usage_counter']} مرة")
                    cnt_lbl.setStyleSheet("color: #3b82f6; font-weight: bold;")
                    
                    r_layout.addWidget(sc_lbl)
                    r_layout.addStretch()
                    r_layout.addWidget(cnt_lbl)
                    self.mu_list_layout.addWidget(row)
        except Exception:
            pass
