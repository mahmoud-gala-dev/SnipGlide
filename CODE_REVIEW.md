# 📋 مراجعة شاملة لكود مشروع SnipGlide Python

> تاريخ المراجعة: أغسطس 2026
> إعداد: مراجعة شاملة للبنية المعمارية، الأداء، الأمان، وتحسينات مقترحة

---

## 📋 نظرة عامة على المشروع

SnipGlide Python هو تطبيق **ملحق نصوص ذكي** (Text Expander) مصمم خصيصًا لنظام Windows، يعمل في الخلفية ويسمح للمستخدم بتوسيق النصوص عبر اختصارات مخصصة. يدعم التطبيق ميزات غنية مثل:

- توسيع الاختصارات النصية (Text Snippet Expansion)
- تصحيح الأخطاء الإملائية تلقائيًا (Autocorrect)
- متابعة الحافظة (Clipboard History)
- ملاحظات مع دعم كتابة عربية (Arabic RTL)
- محادثة نوت بأسلوب واتساب
- بحث موحد عبر كل البيانات
- دعم القوائم المنسدلة والقوالب (Form Prompts)
- دعم المتغيرات الديناميكية (`{{date}}`, `{{time}}`, `{{clipboard}}`, `{{uuid}}`، إلخ)
- دعم تعابير نظامية (Regex Snippets)
- تشفير كلمة مرور رئيسية وحماية الخصوصية
- نسخ احتياطي تلقائي ويدوي

يعتمد على **قواعد بيانات SQLite** محلية (WAL mode) ويدعم تصدير/استيراد عبر JSON، CSV، YAML، والإكسل.

---

## 🏗 بنية المشروع

```
snipglide_python/
├── app.py                            # Entry point (Windows App Icon + run_app)
├── requirements.txt
├── README.md
├── build_exe.bat                     # Build script للـ .exe
├── sample_snippets.json
├── snipglide/
│   ├── main_qt.py                    # PyQt/Qt Entry (AppCoordinatorQt)
│   ├── main.py                       # Tkinter Entry (AppCoordinator - legacy)
│   ├── core/
│   │   └── config.py                 # إعدادات، مسارات، دالة تحميل/حفظ الإعدادات
│   ├── engine/
│   │   ├── listener.py               # ExpansionEngine: حلقة استماع للوحة المفاتيح + التوسيع
│   │   ├── parser.py                 # معالجة المتغييرات والقوالب الديناميكية
│   │   └── window_tracker.py         # الحصول على معلومات النافذة النشطة عبر Win32 API
│   ├── database/
│   │   ├── connection.py             # إنشاء الاتصال SQLite + Initialize schema
│   │   ├── snippet_repo.py           # CRUD للـ Snippets + إحصاءات
│   │   ├── autocorrect_repo.py       # CRUD للـ Autocorrect + بيانات افتراضية
│   │   ├── clipboard_repo.py         # CRUD للـ Clipboard History (50 entries max)
│   │   ├── group_repo.py             # CRUD للـ Groups
│   │   ├── note_repo.py              # CRUD للـ Notes
│   │   ├── note_category_repo.py     # CRUD للـ Note Categories
│   │   ├── note_settings_repo.py     # إعدادات صفحة الملاحظات في الـ DB
│   │   ├── chat_note_repo.py         # CRUD للـ Chat Notes + أقسامها
│   │   └── search_repo.py            # بحث موحد عبر Snippets/Notes/Clipboard
│   ├── services/
│   │   ├── clipboard_monitor.py      # مراقبة الحافظة في خلفية
│   │   ├── auto_backup.py            # نسخ احتياطي يومي تلقائي (7 copies max)
│   │   ├── backup.py                 # صادرات JSON/Excel/YAML/CSV
│   │   ├── plugin_manager.py         # تشغيل بلجينات Python ديناميكي
│   │   ├── security.py               # تشفير كلمة مرور (PBKDF2 + Fernet)
│   │   ├── startup.py                # تسجيل التطبيق في Windows Startup (Registry)
│   ├── ui_qt/                        # واجهة PyQt6
│   │   ├── main_window.py            # النافذة الرئيسية مع Sidebar + Stacked Pages + Tray
│   │   ├── sidebar.py                # شريط جانبي التنقل
│   │   ├── tray_icon.py              # أيقونة النظام (System Tray)
│   │   ├── command_palette.py        # لوحة أوامر سريعة (Ctrl+K)
│   │   ├── quick_paste_bar.py        # شريط لصق سريع (Alt+Space)
│   │   ├── dashboard.py              # لوحة إحصاءات
│   │   ├── snippet_editor_view.py    # محرر الاختصارات
│   │   ├── notes_page.py             # صفحة الملاحظات
│   │   ├── chat_notes_page.py        # صفحة شات نوت
│   │   ├── search_page.py            # صفحة البحث
│   │   ├── clipboard_page.py         # صفحة سجل الحافظة
│   │   ├── styles.py                 # نظام QSS ( stylesheet ) موحد
│   │   ├── web_dev_dialog.py         # مربع أدوات مطور ويب
│   │   ├── email_templates_dialog.py # قوالب بريد إلكتروني
│   │   ├── floating_chat_head.py     # فقاعة دردشة عائمة
│   │   └── widgets/code_editor.py    # محرر أكواد مع Pygments
│   ├── ui/                          # نسخة Tkinter (قد تكون للتراجع)
│   ├── models/
│   │   ├── snippet.py
│   │   ├── note.py
│   │   ├── group.py
│   │   ├── note_category.py
│   │   └── chat_note.py
│   └── utils/
│       ├── logger.py                 # Logger موحد (RotatingFileHandler)
│       ├── helpers.py                # أدوات مساعدة: clipboard API، خط عربي، إلخ
│       └── single_instance.py        # فحص نسخة واحدة فقط عبر Mutex
└── __pycache__/
```

---

## 🧠 التحليل التفصيلي حسب الملف

### 🔧 `app.py`
- **نقطة الدخول الرئيسية**.
- يضيف المسار الحالي إلى `sys.path` لضمان الوجدان الصحيح للوحدات.
- يستخدم `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID` لضبط آيقونة التطبيق في شريط المهام بدلاً من أيقونة Python الافتراضية.
- يستدعي `run_app()` من `main_qt.py`.
- يحتوي على معالجة استثناءات مع طباعة الـ traceback وانتظار إدخال المستخدم قبل الخروج.

**ملاحظة أمنية**: لا يوجد فحص Single Instance — قد يؤدي إلى تشغيل نسخ متعددة من التطبيق.

### 🔧 `snipglide/main_qt.py` — *المنسق الرئيسي للواجهة*
هذا الملف هو **مركز التوحيد بين الواجهة ومحرك التوسيع**.

#### 🏗 الفئة `AppCoordinatorQt`
- **الاستهلال**:
  - `initialize_database()` — إنشاء/تحديث الجداول في SQLite.
  - `load_settings()` — تحميل الإعدادات من `settings.json`.
  - `download_and_load_arabic_font("Tajawal")` — تحميل خط عربي من Google Fonts.
  - إنشاء `HotkeySignalBridge` — جسر إشارة Qt للنقر على المفاتيح العالمية.
  - إنشاء `ExpansionEngine` مع `quick_open_callback` (لإظهار النافذة عند Ctrl+PrintScreen).
  - إنشاء `ClipboardMonitor` كخيط خلفية.

#### 🏃 `run()`
- ينشئ `MainWindowQt`.
- يستدعي `self.window.show()` ويظهرها باستخدام `raise_()` و `activateWindow()`.
- يبدأ `QApplication.exec()` — حلقة الحدث الرئيسية.
- عند الإنهاء: يتوقف `engine` و `clipboard_monitor`.

#### 🔁 `toggle_engine()`
- يبدأ/يوقف `ExpansionEngine` بناءً على الحالة الحالية.

#### 🔄 `notify_snippets_changed()`
- يستدعي `self.engine.reload_snippets()` لتحديث الكاش.

**المشكلة**: لا يتم استدعاء `reload_snippets()` تلقائيًا عند تعديل الاختصارات في الواجهة. يجب ربط `snippets_changed_callback` بشكل صحيح.

---

### 🧩 `snipglide/main.py` (إصدار Tkinter - للتراجع)

> ⚠️ هذا الإصدار القديم قد لا يكون مستخدمًا نشطًا. يفضل حذفه أو توثيقه.

- يدعم:
  - Hotkeys عبر `pynput`
  - أيقونة نظام (System Tray) عبر `pystray`
  - قفل عند بدء التشغيل إذا كانت كلمة مرور مُفعّلة
  - دعم لـ `AppCoordinator` التي تدير كل شيء.

---

### 📦 `snipglide/core/config.py`

#### 📍 المسارات
```python
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "SnipGlidePythonPro"
```
- `DB_FILE` — قاعدة البيانات الرئيسية
- `SETTINGS_FILE` — الإعدادات
- `BACKUP_DIR` — نسخ احتياطية
- `PLUGINS_DIR` — بلجينات مستخدم

#### 🛠️ `DEFAULT_SETTINGS`
الإعدادات الافتراضية الكاملة:

| الفئة | الإعداد | القيمة الافتراضية |
|-------|---------|--------------------|
| 💡 عامة | `enabled` | `True` |
| | `start_minimized` | `False` |
| | `case_sensitive` | `True` |
| | `max_buffer` | `250` |
| | `play_sound` | ❌ **مفقود!** |
| 🔒 أمان | `master_password_enabled` | `False` |
| | `lock_on_startup` | `False` |
| | `master_password_hash` | ❌ **مفقود!** |
| ☁️ تزامن | `sync_enabled` | `False` |
| | `sync_provider` | `"local"` |
| | `sync_path` | `""` |
| 🤖 AI | `ai_api_key` | `""` |
| | `ai_provider` | `"gemini"` |
| 🎨 واجهة | `theme` | `"System"` |
| | `ui_zoom` | `1.0` |
| | `sidebar_font_size` | `13` |
| | `sidebar_direction` | `"ltr"` |
| 📋 حافظة | `clipboard_history_enabled` | `True` |
| | `clipboard_poll_interval` | `3.0` |
| | `clipboard_max_chars` | `10000` |
| | `clipboard_skip_private_windows` | `True` |
| ⌨️ اختصارات | `quick_open_hotkey` | `"<ctrl>+<print_screen>"` |

**المشاكل المكتشفة**:
1. `play_sound` غير مُعرّف رغم استخدامه في `listener.py`.
2. `master_password_hash` و `lock_on_startup` و `master_password_enabled` غير كافية — تحتاج UI لإدارتها.

---

### ⚙️ `snipglide/engine/listener.py` — *القلب النابض للتطبيق*

هذا هو **أكثر جزء معقّدًا وأهم** في المشروع.

#### 🏗 الفئة `ExpansionEngine`

##### 🧠 الاستهلال
- يبني فهرسًا للاختصارات عبر **تخزين مؤقت** مع TTL 5 ثواني.
- يدير:
  - **Buffer نصي** للكبط — يزيد مع كل ضغطة زر، يقلع عند Backspace أو Enter.
  - **نظام حظر/إلغاء تشغيل مؤقت** (`suspended`) خلال عمليات التوسيع.
  - **فحص النافذة النشطة** (لكتشاف النافذ الحساسة مثل login/password).
  - **فحص القائمة السوداء** للبرامج.

##### 🔄 آلية عمل `_on_press`

1. **فحص أولي لطباعة الشاشة + Ctrl**:
   - عندما يُضغط `PrintScreen + Ctrl` → استدعاء `quick_open_callback` لإظهار النافذة.
   - يستخدم `GetAsyncKeyState` مباشرة من Win32 API.

2. **تجاهل المفاتيح** إذا كان المحرك معطل أو مُعلّق.

3. **معالجة Backspace**:
   - حذف آخر حرف من الـ buffer.

4. **معالجة المفاتيح الخاصة** (Space/Enter/Tab/Esc/الأسهم/Delete...):
   - عند Space/Enter/Tab: فحص الـ **autocorrect**.
   - مسح الـ buffer.

5. **إضافة الحرف إلى buffer**:
   - مع الحد الأقصى (`max_buffer = 250`).
   - إذا كان الـ buffer فارغًا ولا يوجد snippets — إرجاع مباشر.

6. **تحميل الكاش** (refreshes كل 5 ثواني).

7. **فحص النافذة النشطة** والـ **blacklist**.

8. **بحث عن أفضل match**:
   - يفضّل الـ snippets الأطول (longest match first).
   - يدعم كل من plain و regex snippets.

9. **استدعاء `_expand`** إذا وُجد match.

##### 🧪 آلية `_expand`

- يستبدد المتغيّرات (`parse_variables`) — يدعم `{{date}}`, `{{time}}`, `{{clipboard}}`, `{{uuid}}`, `{{env:VAR}}`, `{{active_window}}`، إلخ.
- إذا كانت الـ snippet تحتوي على `{{form:field}}` — يستدعي `form_prompt_callback` لعرض نموذج مودال.
- يحذف الـ trigger باستخدام Backspace مرارة (مع تأخير 1ms بين كل ضغطة).
- يكتب النص باستخدام `controller.type()` (يحاكي الكتابة اليدوية — يدعم كل اللغات).
- يرفع عداد الاستخدام (`increment_usage`).
- يلعب صوتًا بسيطًا باستخدام `winsound.Beep(2100, 32)` — **ملاحظة**: `play_sound` غير مُعرّف في DEFAULT_SETTINGS!

##### 🔍 فهرسة الكاش (`_rebuild_snippet_indexes`)

- يقسم الاختصارات إلى:
  - **Plain snippets** — مفهرسة حسب آخر حرف لتسريع البحث.
  - **Regex snippets** — تُترجم إلى `re.compile` مع نمط `$`.
- يحسب `_min_plain_trigger_len` لتسويد الأداء.

##### ⚡ ميزة "Low-Power Mode" (كشف الخمولة)

- إذا لم يتم الضغط على أي مفتاح لمدة 30 ثانية → يُفعّض الـ buffer ويُقلل المعالجة.

---

### 🧩 `snipglide/engine/parser.py`

#### 📝 `parse_variables(text, usage_count)`
يدعم عدة نوع من المتغيّرات:

| المتغيّر | النوع | الوصف |
|----------|-------|-------|
| `{{date}}` / `{date}` | تاريخ | `YYYY-MM-DD` |
| `{{time}}` / `{time}` | وقت | `HH:MM:SS` |
| `{{datetime}}` / `{datetime}` | تاريخ ووقت | `YYYY-MM-DD HH:MM:SS` |
| `{{date:FORMAT}}` | تنسيق مخصص | أي تنسيق `strftime` |
| `{{username}}` | اسم المستخدم | `os.getlogin()` |
| `{{computer}}` / `{{hostname}}` | اسم الجهاز | `socket.gethostname()` |
| `{{clipboard}}` | محتوى الحافظة | `get_clipboard_text()` |
| `{{uuid}}` | معرف فريد | `uuid.uuid4()` |
| `{{random}}` | عدد عشوائي | بين 1000 و 9999 |
| `{{counter}}` | عداد الاستخدام | `usage_count` من الـ DB |
| `{{env:VAR}}` | متغيّر بيئة | أي متغيّر من النظام |
| `{{active_window}}` | عنوان النافذة | النافذة النشطة |

#### 📋 `get_form_fields(text)`
- يستخرج أسماء الحقول من النمط `{{form:field_name}}`.

#### 🔄 `replace_form_fields(text, answers)`
- يستبدل الحقول بالقيم المدخّنة.

---

### 🖥 `snipglide/engine/window_tracker.py`

- يستخدم Win32 API مباشرة عبر `ctypes` للحصول على:
  - عنوان النافذة النشطة (`GetForegroundWindow`, `GetWindowTextW`)
  - اسم العملية (`GetModuleFileNameExW` عبر PSAPI)
- مهم لتطبيق القواعد الأمنية والـ app_filter/window_filter.

---

### 📋 `snipglide/services/clipboard_monitor.py`

- خيط خلفية يراقب التغييرات في الحافظة كل 3 ثوانيات.
- يحفظ النصوص الجديدة في `clipboard_history` (حد أقصى 50 سطرًا).
- يتجاوز النافذة الحساسة (password/login).
- يحترم `blacklist` و `clipboard_max_chars`.
- يستخدم `get_clipboard_text()` من `helpers.py` (Win32 API native).

---

### 🔄 `snipglide/services/auto_backup.py`

- ينشئ نسخة احتياطية يومية من قاعدة البيانات كـ JSON.
- يحتفظ بآخر 7 نسخ فقط.
- يبدأ بعد تأخير 5 ثواني.

---

### 🔒 `snipglide/services/security.py`

- يستخدم:
  - `PBKDF2-HMAC-SHA256` مع 310,000 iteration لتشفير كلمة المرور.
  - `Fernet` (من cryptography library) لتشفير/فك التشفير عبر `get_key_from_password`.
- يدعم وضعية legacy (SHA256) للتوافق للوراء.

**ملاحظة**: `get_key_from_password` يستخدم SHA256 مباشرة — هذا ضعيف نسبيًا للبيانات الحساسة. الأفضل استخدام PBKDF2 هنا أيضًا.

---

### 💾 `snipglide/services/backup.py`

- دوال تصدير/استيراد شاملة:
  - `export_backup/import_backup`: نسخة كاملة من groups + snippets + autocorrect.
  - `export_to_excel/import_from_excel`: دعم ملفات `.xlsx`.
  - `export_to_yaml/import_from_yaml`: صيغة YAML.
  - `export_to_json/import_from_json`: صيغة JSON.
- يتحقق من حجم الملف قبل الاستيراد (`MAX_IMPORT_FILE_BYTES = 25MB`).

---

### 🧩 `snipglide/services/plugin_manager.py`

- يحمّل بلجينات Python ديناميكيًا من مجلد `plugins/`.
- يبحث عن دالة `register_plugin()` في كل ملف.

**ملاحظة أمنية**: لا يوجد sandboxing — البلجينات تعمل بامتيازات كاملة. يجب إضافة warnings في الوثائق.

---

### ⚙️ `snipglide/services/startup.py`

- يُسجّل/يحذف التطبيق من Windows Startup عبر Registry (`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`).
- يفضل `pythonw.exe` من venv، أو `sys.executable`.

---

### 🤖 `snipglide/services/ai.py`

- يدعم دمج Google Gemini API.
- يدعم:
  - `get_available_models`: استعلام نماذج متاحة (مع caching 1 ساعة).
  - `call_ai_completion`: إرسال prompt إلى API مع retry منطقي.
  - `test_ai_key`: اختبار صلاحية API Key.
- يدعم fallback للنماذج الافتراضية إذا فشل الاستعلام.
- يدعم استجابة fallback محلية بسيطة عندما لا يتم توفير API Key.

---

### 🗃 `snipglide/database/connection.py`

- يستخدم `sqlite3.connect` مع:
  - `timeout=10` (لتجنب deadlocks).
  - `PRAGMA journal_mode = WAL` (لدعم قراءة/كتابة متوازية).
  - `PRAGMA synchronous = NORMAL` (توازن بين الأمان والأداء).
  - `PRAGMA cache_size = -32000` (32MB للكاش).
  - `PRAGMA temp_store = MEMORY`.
- `initialize_database()`: يخلق 8 جداول إذا لم تكن موجودة:
  - groups, snippets, autocorrect, clipboard_history, usage_history
  - note_categories, notes, note_settings
  - chat_note_sections, chat_notes
- يضيف فهارس أداء (indexes) على الأعمدة المهمة.
- يُعبّئ تلقائيًا بيانات افتراضية (Default corrections, chat sections بالعربية).

---

### 📂 مستودعات البيانات (Repos)

#### `snippet_repo.py`
- معظم العمليات CRUD على `snippets`.
- دوال مهمة:
  - `get_enabled_snippets`: يُستخدم من قبل `ExpansionEngine`.
  - `get_snippets_for_list`: يدعم البحث + تصفية حسب المجموعة.
  - `increment_usage`: يرفع العداد ويسجل في `usage_history`.
  - `get_statistics`: إحصاءات شاملة (total snippets, most used, daily stats...).

#### `clipboard_repo.py`
- يدير `clipboard_history` بحد أقصى 50 سطرًا.
- `add_clipboard_entry` يحذف التكرارات ويدفع السطر الأحدث للأعلى.

#### `autocorrect_repo.py`
- يدير جدول `autocorrect` مع بيانات افتراضية (إنجليزية + عربية).

#### باقي الـ Repos
- `group_repo.py`, `note_repo.py`, `note_category_repo.py`, `note_settings_repo.py`, `chat_note_repo.py`, `search_repo.py`
- جميعها تتبع نمطًا موحدًا: `get_all`, `get_by_id`, `add`, `update`, `delete`.
- `search_repo` يدعم بحث متكامل عبر 3 مصادر (snippets, notes, clipboard).

---

### 🎨 واجهة المستخدم (Qt UI)

#### `main_window.py` — النافذة الرئيسية
- نافذة Qt كبيرة (1560×960) بدقة عالية.
- Sidebar على اليسار بزران للتنقيل.
- QStackedWidget لعرض الصفحات: Dashboard، Snippets، Notes، ChatNotes، Search، Clipboard.
- **نظام Toast مخصص**: إشعارات منبثقة تظهر/تختفي تلقائيًا.
- أيقونة نظام (System Tray) تبقى شغالة عند إغلاق النافذة.
- اختصارات سريفة:
  - `Ctrl+K` → Command Palette
  - `Alt+Space` → Quick Paste Bar
  - `Ctrl+PrintScreen` → إظهار/إرجاع النافذة
  - `Esc` → تصغير النافذة

#### `sidebar.py`
- شريط جانبي مع 6 أزرار تنقيل.
- أزرار قابلة للتباين (checked/unchecked).

#### `tray_icon.py`
- QSystemTrayIcon مع قائمة سياقية.
- يحتوي على:
  - فتح التطبيق
  - شريط اللصق السريع
  - لوحة الأوامر
  - إظهار/إخفاء فقاعة الشات
  - قائمة منسدلة للاختصارات الأخيرة
  - إغلاق التطبيق

#### `snippet_editor_view.py`
- واجهة مقسمة (Splitter):
  - اليسار: قائمة بالاختصارات مع بحث وتصفية حسب المجموعة.
  - اليمين: نموذج إنشاء/تعديل الاختصار.
- مدعوم بمعاينة حية للتوسيع (Live Preview).
- أزرار لإدراج المتغيّرات السريعة (`{date}`, `{time}`، إلخ).
- إدراج ملفات المنطقة التكطيلية (App filter).

#### `clipboard_page.py`
- سجل الحافظة بتقسيم صفحات (30 عنصر/صفحة).
- زر مسح كامل.

#### `command_palette.py`
- نافذة مودال شفرة (FramelessWindowHint) بحث سريع عن الأوامر والاختصارات والملاحظات.
- دعم تنقل باستخدام الأسهم والـ Enter.

#### `quick_paste_bar.py`
- نافذة شريط سريع آخرى مشابهة للـ Command Palette.
- يدمج بين الاختصارات والحافظة.

#### `styles.py`
- نظام QSS موحد ومُحسّن (Dark Theme افتراضي).
- يدعم `is_dark` للتبديل بين الوضعين.
- استخدام ألوان موحدة (Green accent #25D366، Blue accents للوضع الثانوي).
- دعم خط عربي (Tajawal) وإعدادات حجم الخط الأساسي.

#### `web_dev_dialog.py` و `email_templates_dialog.py`
- أدوات مساعدة مدمجة:
  - **Web Dev Toolbox**: يُنشئ قوالب HTML/CSS/JS جاهزة.
  - **Email Templates**: قوالب بريد إلكتروني احترفية.

#### `chat_notes_page.py` و `floating_chat_head.py`
- **Chat Notes**: محادثة بأسلوب WhatsApp.
  - أقسام قابلة للإدارة (عام، أفكار، مهام، روابط، ملاحظات عمل).
  - emojis لكل قسم.
- **Floating Chat Head**: فقاعة محادثة عائمة على الشاشة.

---

### 📝 الموديلات (Models)
الجميع عبارة عن `@dataclass` بسيطة ومريحة:
- `Snippet`: shortcut, replacement, group_id, tags, enabled, hotkey, regex_enabled, app_filter, window_filter...
- `Note`: title, content, category_id, pinned, color.
- `Group`: name, icon, color, is_collapsed.
- `ChatNote`: content, section_id, tags, color, is_starred.
- `NoteCategory`: name, icon, color, description.

---

## ✅ نقاط قوة بارزة في الكود

1. **أداء ممتاز**:
   - تخزين مؤقت للـ snippets (TTL 5s) لتقليل استعلامات DB.
   - تجميع الاختصارات حسب آخر حرف لتسريع البحث.
   - استخدام WAL mode + فهارس SQLite.
   - كشف الخمولة (idle detection) لتقليل الاستهلاك عند عدم النشاط.

2. **أمان جيد**:
   - تشفير كلمة المرور بـ PBKDF2.
   - تخطيط للنافذ الحساسة (password/login).
   - حماية من صناعة القرارات.

3. **قابلية التوسعة**:
   - نظام بلجينات ديناميكي.
   - صيغة إعدادات مرنة (JSON مع default settings).
   - واجهات برمجة موحدة للـ Repos.

4. **تجربة مستخدم غنية**:
   - Toast Notifications.
   - Live Preview.
   - شريط لصق سريع / لوحة أوامر.
   - دعم كامل للغة العربية (RTL + Font).

5. **موثوقية**:
   - معالجة شاملة للاستثناءات في كل طبقة.
   - نظام Logging مرن (RotatingFileHandler).
   - نسخ احتياطي تلقائي + يدوي.

---

## ⚠️ ملاحظات وتحسينات مقترحة

### 1. Single Instance
- `single_instance.py` موجود لكنه غير مستخدم في `main_qt.py`.
- **الحل المقترح**: إضافته في `run_app()`:
  ```python
  from snipglide.utils.single_instance import SingleInstance
  instance = SingleInstance("snipglide_pro_v2")
  if not instance.is_primary:
      print("SnipGlide is already running.")
      sys.exit(1)
  ```

### 2. استكمال DEFAULT_SETTINGS
- `play_sound` مفقود رغم استخدامه.
- `master_password_hash` و `lock_on_startup` و `master_password_enabled` تحتاج إكمال.

**الحل**: إضافة المفاتيح الافتراضية إلى `DEFAULT_SETTINGS`:
```python
"play_sound": True,
"master_password_hash": "",
```

### 3. إزالة الكود غير المستخدم
- `main.py` (Tkinter) — إما حذفه أو توثيقه كـ legacy.
- `app.pyw` — يبدو كنسخة مكررة.

### 4. تحديث الكاش عند تعديل الاختصارات
- في `main_qt.py`، لا يتم استدعاء `reload_snippets()` تلقائيًا عند تعديل الاختصارات.
- **الحل**: التأكد من ربط `snippets_changed_callback` بـ `_on_snippets_changed` والتي تستدعي `notify_snippets_changed()`.

### 5. تحسين Security
- إضافة UI لإدارة كلمة المرور (تغيير/اختبار).
- استخدام PBKDF2 بدلاً من SHA256 في `get_key_from_password`.

### 6. ملفات التشغيل المتعددة
- `run.bat`, `run.cmd`, `run_app.cmd` — تحتاج فحص لتبسيطها.

### 7. مراجعة SnipGlide.spec و build_exe.bat
- التأكد من شمول جميع الموارد (fonts, icons, data files) في الـ executable.

---

## 🚀 ميزات مقترح إضافتها

### 1. 🎯 Snippet Tags UI
- إضافة واجهة لإدارة التاجات بصريًا.
- فلترة حسب التاج في صفحة الاختصارات.

### 2. 📊 لوحة إحصائيات مطورة
- إضافة رسم بياني لاستخدام الاختصارات يوميًا.
- إحصاءات للـ clipboard history.

### 3. 🔍 بحث ذكي
- إضافة دعم بحث طبيعي اللغة (NLP) — مثال: "اختصار بريدي الأسبوع الماضي".

### 4. 📱 دعم الموبايل
- إنشاء API بسيط لمشاركة الاختصارات مع تطبيق هاتفي.

### 5. 🧠 ذكاء اصطناعي محسن
- دعم إنشاء اختصارات تلقائيًا بناءً على النمط الكتابة.
- دعم تلخيص الملاحظات باستخدام AI.

### 6. 🗂 إدارة النسخ الاحتياطي السحابية
- دمج Google Drive أو Dropbox بدلاً من `sync_provider = "local"`.

### 7. 🪟 وضع مظلم/فاتح تلقائي
- استخدام `darkdetect` للكشف عن وضع النظام وتطبيقه.

### 8. 🧾 دليل مستخدم تفاعلي
- إضافة نظام Help داخل التطبيق (بوحدة "Help" في الـ Sidebar).

---

## 📊 رسم معماري للبنية

```
┌────────────────────────────────────────────┐
│           Entry Point (app.py)              │
│    Windows Icon Setup + Error Handling     │
└──────────────┬─────────────────────────────┘
               ▼
┌────────────────────────────────────────────┐
│         main_qt.py (AppCoordinatorQt)     │
│  • Initialize DB                        │
│  • Load Settings                        │
│  • Load Arabic Font                     │
│  • Start ExpansionEngine                │
│  • Start ClipboardMonitor               │
│  • Create MainWindowQt                  │
└──────────────┬─────────────────────────────┘
               ▼
┌────────────────────────────────────────────┐
│              UI Layer (ui_qt/)             │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Sidebar │ │   Pages  │ │   TrayIcon   │  │
│  │         │ │ (Stacked)│ │              │  │
│  └─────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐ │
│  │ CmdPalette│ │ QuickPasteBar│ │ ToastLabel  │ │
│  └──────────┘ └────────────┘ └────────────┘ │
└──────────────┬──────────────────────────────┘
               ▼
┌────────────────────────────────────────────┐
│         Engine Layer (engine/)             │
│  ┌──────────────┐ ┌────────────┐          │
│  │ ExpansionEngine│ │  Parser     │          │
│  │  (Listener)   │ │ (Variables) │          │
│  └──────────────┘ └────────────┘          │
│  ┌────────────────────────────┐           │
│  │ WindowTracker (Win32 API)   │           │
│  └────────────────────────────┘           │
└──────────────┬────────────────────────────┘
               ▼
┌────────────────────────────────────────────┐
│         Services Layer (services/)         │
│  ┌────────────┐ ┌────────────┐ ┌───────┐ │
│  │ClipboardMon│ │ AutoBackup │ │Security│ │
│  │ itor       │ │            │ │       │ │
│  └────────────┘ └────────────┘ └───────┘ │
│  ┌────────────┐ ┌────────────┐ ┌───────┐ │
│  │ PluginMgr  │ │ StartupMgr │ │ AI    │ │
│  └────────────┘ └────────────┘ └───────┘ │
│  ┌────────────────────────────┐         │
│  │ Exporter/Importer (JSON,YAML,CSV,XLSX) ││
│  └────────────────────────────┘         │
└──────────────┬────────────────────────────┘
               ▼
┌────────────────────────────────────────────┐
│    Database Layer (database/)             │
│  ┌────────────┐ ┌────────┐ ┌───────────┐ │
│  │ connection │ │ repos  │ │ models    │ │
│  │ (SQLite)   │ │        │ │           │ │
│  └────────────┘ └────────┘ └───────────┘ │
└────────────────────────────────────────────┘
```

---

## 🏆 الخلاصة العامة

SnipGlide Python هو تطبيق **احترافي بامتياز** ببنية نظيفة، أداء ممتاز، ودعم شامل للغة العربية. يقدّر:

- **فصل الاهتمامات** (Separation of Concerns) جيد.
- **إعادة الاستخدام** (Reusability) عبر الموديلات والـ Repos.
- **قابلية الصيانة** بفضل الكود المنظم والوثائق.
- **تجربة مستخدم غنية** تشبه تطبيقات SaaS احترافية.

### 🔑 ملاحظات أمنية وهامة
- `single_instance.py` غير مستخدم — يجب تفعيله لمنع التشغيل المتعدد غير المقصود.
- `play_sound` و `master_password_hash` مفقودان من DEFAULT_SETTINGS — سيؤديان إلى سلوك غير متوقع.
- يُنصح بمراجعة `SnipGlide.spec` و `build_exe.bat` لضمان شمول كل الملفات المطلوبة.
- `app.pyw` يجب حذفه أو دمجه لتجنب الالتباك.

### 🚀 توصيات للتطوير المستقبلي:
1. إضافة `SingleInstance` إلى `main_qt.py`.
2. إكمال `DEFAULT_SETTINGS` بجميع المفاتيح المستخدمة.
3. إزالة الكود غير المستخدم (`main.py`، `app.pyw`).
4. إضافة UI لإدارة كلمة المرور.
5. مراجعة وتوحيد إعدادات الاختصارات العامة (Ctrl+Alt+S، Ctrl+PrintScreen...).

---

## 📎 ملاحق

### 🧪 فحص أداء التحميل (Startup Profile)
- تحميل الخط العربي يحدث في خيط منفصل — جيد.
- تحميل الـ snippets يحدث في كاش مع تجديد كل 5 ثواني — ممتاز.
- مراقبة الحافظة كل 3 ثواني — مناسب.

### 🐛 بحث عن مشاكل محتملة
| المكان | المشكلة | الحالة |
|--------|---------|--------|
| `listener.py:352` | `play_sound` غير مُعرّف في الإعدادات الافتراضية | ⚠️ محتمل |
| `main.py:77` | استخدام `withdraw` في Tkinter قد يتعارض مع Qt | ⚠️ كود قديم |
| `security.py:37` | `get_key_from_password` يستخدم SHA256 مباشرة | ⚠️ مراجعة أمنية |
| `plugin_manager.py` | تحميل بلجينات غير موثوقة بامتيازات كاملة | ⚠️ توثيق مطلوب |

### 📦 الاعتماديات (requirements.txt)
```
PySide6>=6.6.0          # واجهة Qt6
pynput>=1.7.7            # الاستماع لوحة المفاتيح
sounddevice>=0.5.0       # معالجة الصوت
soundfile>=0.14.0        # قراءة ملفات صوتية
numpy>=2.0.0             # معالجة إشارة
Pillow>=10.0.0           # معالجة صور (System Tray Icon)
cryptography>=41.0.0     # تشفير كلمة المرور
pyyaml>=6.0.0            # استيراد YAML
openpyxl>=3.1.0          # دعم Excel
pygments>=2.15.0         # تلوين الكود
arabic-reshaper>=3.0.0   # دعم النص العربي
python-bidi>=0.4.2       # اتجاه النص العربي
watchdog>=3.0.0          # مراقبة ملفات الـ sync
darkdetect>=0.8.0        # اكتشاف وضع النظام
```

> ملاحظة: `pystray` و `customtkinter` مستخدمان في `main.py` (Tkinter) فقط — قد يتم إزالتهما إذا لم يتم استخدامهما.