from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton, QProgressBar, QApplication
)

from snipglide.database.snippet_repo import get_statistics, get_all_snippets
from snipglide.database.note_repo import get_notes_count
from snipglide.database.chat_note_repo import get_chat_notes_count
from snipglide.database.clipboard_repo import get_clipboard_history_count

class DashboardQt(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        # ── Header Title & Refresh ──
        header_row = QHBoxLayout()

        btn_drawer = QPushButton("☰ القائمة")
        btn_drawer.setToolTip("إظهار / إخفاء القائمة الجانبية (Drawer) - Ctrl+B")
        btn_drawer.setCursor(QCursor(Qt.PointingHandCursor))
        btn_drawer.setStyleSheet("""
            QPushButton {
                background-color: #182229;
                color: #60a5fa;
                border: 1.5px solid #2a3942;
                border-radius: 9px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #172554;
                color: #93c5fd;
                border-color: #3b82f6;
            }
        """)
        btn_drawer.clicked.connect(lambda: self.window().toggle_sidebar() if hasattr(self.window(), "toggle_sidebar") else None)
        header_row.addWidget(btn_drawer)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("📊 لوحة الأداء والإنتاجية (Analytics & Overview)")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: #f0f2f5;")
        subtitle = QLabel("نظرة شاملة وسريعة على اختصاراتك، ملاحظاتك، والوقت الموفّر أثناء الكتابة.")
        subtitle.setStyleSheet("font-size: 14px; color: #94a3b8;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box)
        header_row.addStretch()

        ref_btn = QPushButton("🔄 تحديث الأرقام")
        ref_btn.setFixedHeight(42)
        ref_btn.setCursor(QCursor(Qt.PointingHandCursor))
        ref_btn.setStyleSheet("""
            QPushButton {
                background-color: #202c33;
                border: 1.5px solid #3b4a54;
                color: #f0f2f5;
                font-weight: bold;
                font-size: 14px;
                border-radius: 10px;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #2a3942;
                border-color: #25D366;
            }
        """)
        ref_btn.clicked.connect(self.refresh_stats)
        header_row.addWidget(ref_btn)
        main_layout.addLayout(header_row)

        # ── 6 Glowing Metric Cards ──
        cards_grid = QHBoxLayout()
        cards_grid.setSpacing(14)

        self.card_snippets = self._create_metric_card("✂️ الاختصارات", "0", "#25D366", "إجمالي القوالب النشطة")
        self.card_chat = self._create_metric_card("💬 رسائل الشات", "0", "#38bdf8", "ملاحظات الشات السريعة")
        self.card_notes = self._create_metric_card("📝 الملاحظات", "0", "#f59e0b", "مستودع الملاحظات")
        self.card_expansions = self._create_metric_card("⚡ التوسيعات", "0", "#a855f7", "عدد مرات التوسيع")
        self.card_time = self._create_metric_card("⏱️ الوقت الموفّر", "0 دقيقة", "#ec4899", "وقت الكتابة المسترجع")
        self.card_clip = self._create_metric_card("📋 الحافظة", "0", "#06b6d4", "عناصر السجل المكتشفة")

        cards_grid.addWidget(self.card_snippets)
        cards_grid.addWidget(self.card_chat)
        cards_grid.addWidget(self.card_notes)
        cards_grid.addWidget(self.card_expansions)
        cards_grid.addWidget(self.card_time)
        cards_grid.addWidget(self.card_clip)
        main_layout.addLayout(cards_grid)

        # ── Quick Action Hub ──
        hub_frame = QFrame()
        hub_frame.setObjectName("hubFrame")
        hub_frame.setStyleSheet("""
            QFrame#hubFrame {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 14px;
            }
        """)
        hub_layout = QHBoxLayout(hub_frame)
        hub_layout.setContentsMargins(18, 12, 18, 12)
        hub_layout.setSpacing(12)

        hub_title = QLabel("⚡ الإجراءات الفورية:")
        hub_title.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 14px; background: transparent; border: none;")
        hub_layout.addWidget(hub_title)

        btn_snip = self._create_hub_button("➕ اختصار جديد", "#25D366", lambda: self._navigate("Snippets", new_snip=True))
        btn_chat = self._create_hub_button("💬 كتابة في الشات", "#38bdf8", lambda: self._navigate("ChatNotes"))
        btn_cmd = self._create_hub_button("⌨️ لوحة الأوامر (Ctrl+K)", "#a855f7", self._open_cmd)
        btn_paste = self._create_hub_button("🚀 شريط اللصق (Alt+Space)", "#f59e0b", self._open_paste)

        hub_layout.addWidget(btn_snip)
        hub_layout.addWidget(btn_chat)
        hub_layout.addWidget(btn_cmd)
        hub_layout.addWidget(btn_paste)
        hub_layout.addStretch()
        main_layout.addWidget(hub_frame)

        # ── Two-Column Lower Section ──
        lower_row = QHBoxLayout()
        lower_row.setSpacing(18)

        # Left Column: Most Used Snippets
        mu_frame = QFrame()
        mu_frame.setObjectName("muFrame")
        mu_frame.setStyleSheet("""
            QFrame#muFrame {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 14px;
            }
        """)
        mu_layout = QVBoxLayout(mu_frame)
        mu_layout.setContentsMargins(18, 16, 18, 16)
        mu_layout.setSpacing(10)

        mu_head = QLabel("🏆 الاختصارات الأكثر استخداماً (Top Snippets)")
        mu_head.setStyleSheet("font-size: 16px; font-weight: bold; color: #f0f2f5; background: transparent; border: none;")
        mu_layout.addWidget(mu_head)

        self.mu_container = QWidget()
        self.mu_list_layout = QVBoxLayout(self.mu_container)
        self.mu_list_layout.setSpacing(8)
        self.mu_list_layout.setContentsMargins(0, 0, 0, 0)

        mu_scroll = QScrollArea()
        mu_scroll.setWidgetResizable(True)
        mu_scroll.setStyleSheet("background: transparent; border: none;")
        mu_scroll.setWidget(self.mu_container)
        mu_layout.addWidget(mu_scroll, stretch=1)
        lower_row.addWidget(mu_frame, stretch=3)

        # Right Column: Productivity Insights
        insights_frame = QFrame()
        insights_frame.setObjectName("insightsFrame")
        insights_frame.setStyleSheet("""
            QFrame#insightsFrame {
                background-color: #111b21;
                border: 1.5px solid #202c33;
                border-radius: 14px;
            }
        """)
        in_layout = QVBoxLayout(insights_frame)
        in_layout.setContentsMargins(18, 16, 18, 16)
        in_layout.setSpacing(12)

        in_head = QLabel("💡 معدل الإنتاجية وتوفير النقرات")
        in_head.setStyleSheet("font-size: 16px; font-weight: bold; color: #f0f2f5; background: transparent; border: none;")
        in_layout.addWidget(in_head)

        self.keystrokes_lbl = QLabel("⌨️ النقرات الموفّرة: 0 نقرة")
        self.keystrokes_lbl.setStyleSheet("font-size: 15px; color: #25D366; font-weight: bold; background: transparent; border: none;")
        in_layout.addWidget(self.keystrokes_lbl)

        self.speed_boost_lbl = QLabel("🚀 تسريع الكتابة المقدر: +140%")
        self.speed_boost_lbl.setStyleSheet("font-size: 15px; color: #38bdf8; font-weight: bold; background: transparent; border: none;")
        in_layout.addWidget(self.speed_boost_lbl)

        # Productivity Progress Bar
        bar_title = QLabel("كفاءة استخدام القوالب:")
        bar_title.setStyleSheet("font-size: 13px; color: #94a3b8; background: transparent; border: none;")
        in_layout.addWidget(bar_title)

        self.prod_bar = QProgressBar()
        self.prod_bar.setFixedHeight(18)
        self.prod_bar.setValue(88)
        self.prod_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0b141a;
                border: 1px solid #202c33;
                border-radius: 9px;
                text-align: center;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #38bdf8);
                border-radius: 8px;
            }
        """)
        in_layout.addWidget(self.prod_bar)

        in_layout.addStretch()

        # Engine Status Box
        status_box = QFrame()
        status_box.setObjectName("statusBox")
        status_box.setStyleSheet("""
            QFrame#statusBox {
                background-color: #0b141a;
                border: 1px solid #202c33;
                border-radius: 10px;
            }
        """)
        s_layout = QHBoxLayout(status_box)
        s_layout.setContentsMargins(12, 8, 12, 8)

        dot = QLabel("🟢")
        dot.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        s_layout.addWidget(dot)

        st_lbl = QLabel("محرك التوسيع يعمل بسلاسة في الخلفية (Active)")
        st_lbl.setStyleSheet("color: #22c55e; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        s_layout.addWidget(st_lbl)
        s_layout.addStretch()

        in_layout.addWidget(status_box)
        lower_row.addWidget(insights_frame, stretch=2)

        main_layout.addLayout(lower_row, stretch=1)
        self.refresh_stats()

    def _create_metric_card(self, title: str, val: str, border_color: str, sub: str) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        card.setMinimumHeight(130)
        card.setStyleSheet(f"""
            QFrame#metricCard {{
                background-color: #111b21;
                border-radius: 14px;
                border: 1.5px solid #202c33;
                border-top: 4px solid {border_color};
            }}
            QFrame#metricCard:hover {{
                border-color: {border_color};
                background-color: #182229;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(6)
        c_layout.setAlignment(Qt.AlignTop)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 14px; color: #94a3b8; font-weight: bold; background: transparent; border: none;")

        v_lbl = QLabel(val)
        v_lbl.setStyleSheet("font-size: 28px; font-weight: 800; color: #f0f2f5; background: transparent; border: none;")

        s_lbl = QLabel(sub)
        s_lbl.setStyleSheet("font-size: 12px; color: #64748b; background: transparent; border: none;")

        c_layout.addWidget(t_lbl)
        c_layout.addWidget(v_lbl)
        c_layout.addWidget(s_lbl)
        card.value_label = v_lbl
        return card

    def _create_hub_button(self, text: str, hover_color: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(38)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #202c33;
                color: #f0f2f5;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #3b4a54;
                border-radius: 8px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background-color: #2a3942;
                border-color: {hover_color};
                color: {hover_color};
            }}
        """)
        btn.clicked.connect(callback)
        return btn

    def _navigate(self, page_id: str, new_snip: bool = False):
        if self.main_window:
            self.main_window.sidebar.select_page(page_id)
            if new_snip and hasattr(self.main_window, "snippets_page"):
                self.main_window.snippets_page.new_snippet()

    def _open_cmd(self):
        if self.main_window and hasattr(self.main_window, "open_command_palette"):
            self.main_window.open_command_palette()

    def _open_paste(self):
        if self.main_window and hasattr(self.main_window, "open_quick_paste_bar"):
            self.main_window.open_quick_paste_bar()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_stats()

    def refresh_stats(self):
        try:
            stats = get_statistics()
            total_snippets = stats.get("total_snippets", 0)
            total_expansions = stats.get("total_expansions", 0)
            total_chat = get_chat_notes_count()
            total_notes = get_notes_count()
            total_clip = get_clipboard_history_count()

            # Calculate time & keystrokes saved (assuming ~45 chars per expansion, 200 CPM typing speed)
            chars_saved = max(total_expansions * 45, 120)
            minutes_saved = (chars_saved / 200)
            time_str = f"{minutes_saved:.1f} دقيقة" if minutes_saved < 60 else f"{(minutes_saved / 60):.1f} ساعة"

            self.card_snippets.value_label.setText(str(total_snippets))
            self.card_chat.value_label.setText(str(total_chat))
            self.card_notes.value_label.setText(str(total_notes))
            self.card_expansions.value_label.setText(str(total_expansions))
            self.card_time.value_label.setText(time_str)
            self.card_clip.value_label.setText(str(total_clip))

            self.keystrokes_lbl.setText(f"⌨️ النقرات الموفّرة: {chars_saved:,} نقرة")
            pct = min(100, max(25, int(total_expansions * 3.5)))
            self.prod_bar.setValue(pct)
            self.speed_boost_lbl.setText(f"🚀 تسريع الكتابة المقدر: +{min(350, 40 + total_expansions * 5)}%")

            while self.mu_list_layout.count():
                item = self.mu_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            most_used = stats.get("most_used", [])
            if not most_used:
                no_lbl = QLabel("لا توجد إحصائيات مسجلة بعد. استخدم أي اختصار لتبدأ الأرقام بالتسجيل فوراً!")
                no_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 15px; border: none;")
                self.mu_list_layout.addWidget(no_lbl)
            else:
                for item in most_used:
                    row = QFrame()
                    row.setStyleSheet("""
                        QFrame {
                            background-color: #182229;
                            border: 1.5px solid #2a3942;
                            border-radius: 10px;
                            padding: 8px 12px;
                        }
                        QFrame:hover {
                            border-color: #3b82f6;
                            background-color: #202c33;
                        }
                    """)
                    r_layout = QHBoxLayout(row)
                    r_layout.setContentsMargins(12, 8, 12, 8)
                    r_layout.setSpacing(10)

                    sc_lbl = QLabel(f"✂️ {item['shortcut']}")
                    sc_lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #f0f2f5; border: none;")
                    r_layout.addWidget(sc_lbl)

                    r_layout.addStretch()

                    cnt_badge = QLabel(f"{item['usage_counter']} مرة استخدام")
                    cnt_badge.setStyleSheet("background-color: #1e3a8a; color: #93c5fd; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 4px 12px; border: none;")
                    r_layout.addWidget(cnt_badge)

                    self.mu_list_layout.addWidget(row)
        except Exception as e:
            from snipglide.utils.logger import logger
            logger.error(f"Dashboard refresh error: {e}")
