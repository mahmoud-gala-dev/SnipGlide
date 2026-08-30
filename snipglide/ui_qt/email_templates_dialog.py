from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QPlainTextEdit, QLineEdit, QApplication,
    QSplitter
)

EMAIL_TEMPLATES = [
    {
        "title": "📧 رد ترحيبي وتأكيد استلام الطلب",
        "category": "خدمة العملاء",
        "body": """السلام عليكم ورحمة الله وبركاته،

أهلاً بك {client_name}،
نشكرك على تواصلك معنا بخصوص {subject}.

نود إعلامك بأنه تم استلام طلبك بنجاح وجارٍ مراجعته من قبل الفريق المختص وسنوافيك بالتحديثات خلال 24 ساعة بإذن الله.

مع خالص التحية والتقدير،
{my_name}
{company}"""
    },
    {
        "title": "📅 تأكيد ومتابعة موعد اجتماع",
        "category": "الأعمال والإدارة",
        "body": """تحية طيبة {client_name}،

نود تذكيرك بموعد اجتماعنا المقرر يوم {date} في تمام الساعة {meeting_time}.
رابط الاجتماع / المكان: {meeting_link}

جدول الأعمال:
1. مناقشة أحدث المستجدات في {subject}.
2. تحديد الخطوات القادمة وتوزيع المهام.

نتطلع للقائك،
{my_name}"""
    },
    {
        "title": "💼 إرسال عرض سعر ومتابعة",
        "category": "المبيعات",
        "body": """السلام عليكم ورحمة الله وبركاته {client_name}،

بناءً على تواصلنا السابق، يسرنا أن نرفق لك عرض السعر الخاص بـ {subject}.
لقد حرصنا على توفير أفضل الحلول التقنية والمالية التي تلبي متطلباتكم بدقة.

العرض ساري حتى تاريخ: {date}
نحن على أتم الاستعداد للإجابة عن أي استفسار أو عقد جلسة لمناقشة التفاصيل.

دمتم بخير،
{my_name}
{company}"""
    },
    {
        "title": "🌴 طلب إجازة رسمي",
        "category": "الموارد البشرية",
        "body": """السيد/ة مدير الموارد البشرية المحترم/ة،

أرجو التكرم بالموافقة على طلبي للحصول على إجازة اعتيادية لمدة {days_count} أيام، تبدأ من تاريخ {date} وحتى {end_date}.
تم التنسيق مع الزملاء لتغطية كافة المهام العاجلة أثناء فترة غيابي.

شاكراً لكم حسن تعاونكم الدائم،
{my_name}
القسم: {department}"""
    },
    {
        "title": "⚠️ اعتذار مهني عن تأخير مع الحل البديل",
        "category": "إدارة المشاريع",
        "body": """عزيزي {client_name}،

نعتذر بصدق عن أي تأخير غير مقصود في تسليم {subject}.
نظراً لبعض التحديات التقنية غير المتوقعة، نحتاج إلى مهلة إضافية حتى تاريخ {date} لضمان تقديم العمل بأعلى معايير الجودة المطلوبة.

نقدر تفهمكم وصبركم، ونحن ملتزمون بتعويضكم وتسليم المشروع على أكمل وجه.

مع وافر الاحترام،
{my_name}"""
    }
]

class EmailTemplatesDialogQt(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("قوالب البريد الإلكتروني الذكية (Smart Email Templates)")
        self.resize(950, 600)
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header
        h_row = QHBoxLayout()
        title = QLabel("📧 قوالب البريد الإلكتروني الذكية (Smart Email Templates)")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f0f2f5;")
        h_row.addWidget(title)
        h_row.addStretch()
        main_layout.addLayout(h_row)

        splitter = QSplitter(Qt.Horizontal)

        # Left List
        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 10px; border: 1.5px solid #2a3942;")
        l_layout = QVBoxLayout(left_frame)
        l_layout.setContentsMargins(8, 8, 8, 8)
        l_layout.setSpacing(10)

        l_head = QLabel("اختر القالب:")
        l_head.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 13px;")
        l_layout.addWidget(l_head)

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
        self.list_widget.currentRowChanged.connect(self._on_template_selected)
        l_layout.addWidget(self.list_widget)
        splitter.addWidget(left_frame)

        # Right Preview & Fill
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: #111b21; border-radius: 12px; padding: 14px; border: 1.5px solid #2a3942;")
        r_layout = QVBoxLayout(right_frame)
        r_layout.setContentsMargins(14, 12, 14, 12)
        r_layout.setSpacing(10)

        # Variable Inputs Row
        var_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("اسم المستلم (client_name)")
        self.name_edit.setFixedHeight(38)
        self.name_edit.textChanged.connect(self._render_template)
        var_row.addWidget(self.name_edit)

        self.sub_edit = QLineEdit()
        self.sub_edit.setPlaceholderText("موضوع الإيميل (subject)")
        self.sub_edit.setFixedHeight(38)
        self.sub_edit.textChanged.connect(self._render_template)
        var_row.addWidget(self.sub_edit)
        r_layout.addLayout(var_row)

        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b141a;
                color: #f0f2f5;
                font-size: 15px;
                border-radius: 10px;
                padding: 14px;
                border: 2px solid #3b4a54;
            }
        """)
        r_layout.addWidget(self.preview_edit, stretch=1)

        # Bottom Buttons
        bot_row = QHBoxLayout()
        bot_row.addStretch()

        copy_btn = QPushButton("📋 نسخ الإيميل بالكامل")
        copy_btn.setFixedHeight(44)
        copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        copy_btn.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; border-radius: 10px; padding: 4px 24px; font-size: 14px;")
        copy_btn.clicked.connect(self._copy_email)
        bot_row.addWidget(copy_btn)

        r_layout.addLayout(bot_row)
        splitter.addWidget(right_frame)
        splitter.setSizes([320, 600])
        main_layout.addWidget(splitter)

    def _populate_list(self):
        for t in EMAIL_TEMPLATES:
            item = QListWidgetItem(f"{t['title']}\n[{t['category']}]")
            item.setData(Qt.UserRole, t["body"])
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_template_selected(self, row):
        if row >= 0:
            self._render_template()

    def _render_template(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        template_raw = item.data(Qt.UserRole)
        c_name = self.name_edit.text().strip() or "[اسم المستلم]"
        sub = self.sub_edit.text().strip() or "[موضوع الرسالة]"
        today = datetime.now().strftime("%Y-%m-%d")

        rendered = template_raw.replace("{client_name}", c_name)
        rendered = rendered.replace("{subject}", sub)
        rendered = rendered.replace("{date}", today)
        rendered = rendered.replace("{my_name}", "أحمد / SnipGlide User")
        rendered = rendered.replace("{company}", "SnipGlide Solutions")
        rendered = rendered.replace("{meeting_time}", "10:00 صباحاً")
        rendered = rendered.replace("{meeting_link}", "https://meet.google.com/xyz-abcd-efg")
        rendered = rendered.replace("{days_count}", "3")
        rendered = rendered.replace("{end_date}", "2026-09-05")
        rendered = rendered.replace("{department}", "قسم التقنية والتطوير")

        self.preview_edit.setPlainText(rendered)

    def _copy_email(self):
        text = self.preview_edit.toPlainText()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
        self.accept()
