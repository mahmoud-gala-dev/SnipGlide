from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QPlainTextEdit, QApplication,
    QSplitter, QComboBox
)

from snipglide.database.snippet_repo import add_snippet
from snipglide.models.snippet import Snippet

WEB_DEV_SNIPPETS = [
    {
        "title": "⚛️ React TypeScript Functional Component",
        "category": "React / Next.js",
        "shortcut": "@rfc",
        "code": """import React from 'react';

interface Props {
  title: string;
  children?: React.ReactNode;
}

export const ComponentName: React.FC<Props> = ({ title, children }) => {
  return (
    <div className="p-4 rounded-xl bg-slate-900 text-white shadow-lg">
      <h2 className="text-xl font-bold mb-2">{title}</h2>
      {children}
    </div>
  );
};
"""
    },
    {
        "title": "⚡ Async API Fetch Handler with Error Handling",
        "category": "JavaScript / TypeScript",
        "shortcut": "@fetch",
        "code": """async function fetchData<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json() as T;
  } catch (error) {
    console.error('Fetch failed:', error);
    return null;
  }
}
"""
    },
    {
        "title": "🎨 Tailwind Modern Glassmorphism Card",
        "category": "CSS & Tailwind",
        "shortcut": "@glass",
        "code": """<div className="relative backdrop-blur-md bg-white/10 dark:bg-black/20 border border-white/20 dark:border-white/10 rounded-2xl p-6 shadow-2xl transition-all duration-300 hover:scale-[1.02]">
  <h3 className="text-lg font-semibold text-white">Title</h3>
  <p className="text-sm text-slate-300 mt-2">Description text goes here...</p>
</div>
"""
    },
    {
        "title": "🐬 Express.js REST API Router Template",
        "category": "Backend & API",
        "shortcut": "@router",
        "code": """import { Router, Request, Response } from 'express';

const router = Router();

router.get('/', async (req: Request, res: Response) => {
  try {
    res.json({ success: true, message: 'OK' });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
"""
    },
    {
        "title": "🐙 Git Quick Reset & Clean Local Branch",
        "category": "Git & DevOps",
        "shortcut": "@gitclean",
        "code": """git reset --hard HEAD
git clean -fd
git fetch origin
git pull --rebase
"""
    },
    {
        "title": "🐳 Multi-Stage Dockerfile for Node / Next.js",
        "category": "Git & DevOps",
        "shortcut": "@dockerfile",
        "code": """FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM base AS runner
WORKDIR /app
COPY --from=base /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
"""
    }
]

class WebDevDialogQt(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ مستودع أكواد مبرمج الويب (Web Developer Toolbox)")
        self.resize(1000, 620)
        self._setup_ui()
        self._populate_categories()
        self._filter_list()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header
        h_row = QHBoxLayout()
        title = QLabel("🛠️ مستودع أكواد وأدوات مبرمج الويب (Web Developer Library)")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f0f2f5;")
        h_row.addWidget(title)
        h_row.addStretch()

        self.cat_filter = QComboBox()
        self.cat_filter.setFixedHeight(38)
        self.cat_filter.setMinimumWidth(180)
        self.cat_filter.currentTextChanged.connect(self._filter_list)
        h_row.addWidget(self.cat_filter)
        main_layout.addLayout(h_row)

        splitter = QSplitter(Qt.Horizontal)

        # Left List
        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 10px; border: 1.5px solid #2a3942;")
        l_layout = QVBoxLayout(left_frame)
        l_layout.setContentsMargins(8, 8, 8, 8)
        l_layout.setSpacing(8)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #0b141a;
                border: 1px solid #202c33;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #182229;
                color: #f0f2f5;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 4px;
                border: 1px solid #2a3942;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #202c33;
            }
            QListWidget::item:selected {
                background-color: #172554;
                color: #93c5fd;
                border: 1.5px solid #3b82f6;
            }
        """)
        self.list_widget.currentRowChanged.connect(self._on_snippet_selected)
        l_layout.addWidget(self.list_widget)
        splitter.addWidget(left_frame)

        # Right Code Viewer
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 14px; border: 1.5px solid #2a3942;")
        r_layout = QVBoxLayout(right_frame)
        r_layout.setContentsMargins(14, 12, 14, 12)
        r_layout.setSpacing(10)

        # Top Bar
        tb_row = QHBoxLayout()
        self.shortcut_badge = QLabel("")
        self.shortcut_badge.setStyleSheet("background-color: #1e3a8a; color: #93c5fd; font-weight: bold; padding: 4px 12px; border-radius: 6px;")
        tb_row.addWidget(self.shortcut_badge)
        tb_row.addStretch()

        self.add_to_snips_btn = QPushButton("➕ إضافة لقائمة اختصاراتي")
        self.add_to_snips_btn.setFixedHeight(36)
        self.add_to_snips_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.add_to_snips_btn.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; border-radius: 8px; padding: 4px 16px;")
        self.add_to_snips_btn.clicked.connect(self._add_to_user_snippets)
        tb_row.addWidget(self.add_to_snips_btn)
        r_layout.addLayout(tb_row)

        self.code_edit = QPlainTextEdit()
        self.code_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b141a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                border-radius: 10px;
                padding: 14px;
                border: 2px solid #2a3942;
            }
        """)
        r_layout.addWidget(self.code_edit, stretch=1)

        # Bottom Copy Button
        bot_row = QHBoxLayout()
        bot_row.addStretch()

        copy_btn = QPushButton("📋 نسخ الكود البرمجي فوراً")
        copy_btn.setFixedHeight(44)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; border-radius: 10px; padding: 4px 26px; font-size: 15px;")
        copy_btn.clicked.connect(self._copy_code)
        bot_row.addWidget(copy_btn)

        r_layout.addLayout(bot_row)
        splitter.addWidget(right_frame)
        splitter.setSizes([340, 640])
        main_layout.addWidget(splitter)

    def _populate_categories(self):
        cats = sorted(list(set(s["category"] for s in WEB_DEV_SNIPPETS)))
        self.cat_filter.addItem("📂 كافة الأقسام (All Categories)")
        for c in cats:
            self.cat_filter.addItem(f"📁 {c}")

    def _filter_list(self):
        self.list_widget.clear()
        selected_cat = self.cat_filter.currentText()

        for s in WEB_DEV_SNIPPETS:
            if "كافة الأقسام" in selected_cat or selected_cat.replace("📁 ", "") == s["category"]:
                item = QListWidgetItem(f"{s['title']}\n[{s['shortcut']}]")
                item.setData(Qt.UserRole, s)
                self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_snippet_selected(self, row):
        item = self.list_widget.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole)
        self.code_edit.setPlainText(data["code"])
        self.shortcut_badge.setText(f"رمز الاختصار: {data['shortcut']}")

    def _copy_code(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.code_edit.toPlainText())
        self.accept()

    def _add_to_user_snippets(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole)
        snip = Snippet(
            shortcut=data["shortcut"],
            replacement=data["code"],
            description=data["title"],
        )
        try:
            add_snippet(snip)
            self.add_to_snips_btn.setText("✓ تمت الإضافة بنجاح!")
            self.add_to_snips_btn.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold; border-radius: 8px; padding: 4px 16px;")
        except Exception:
            pass
