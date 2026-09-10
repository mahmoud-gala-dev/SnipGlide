# 🚀 SnipGlide Python Pro

<div align="center">

![SnipGlide Logo](https://raw.githubusercontent.com/mahmoud-gala-dev/SnipGlide/main/snipglide/assets/icon.ico)

### **The All-in-One Desktop Productivity Suite for Windows**
**تطبيق الإنتاجية الشامل: توسيع النصوص الذكي، التقاط وتسجيل الشاشة فيديو، إدارة المجلدات بالسحب والإفلات، والمفكرة المتقدمة.**

[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/PySide6-Qt6-green?style=for-the-badge&logo=qt)](https://www.qt.io/)
[![Database](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?style=for-the-badge&logo=sqlite)](https://www.sqlite.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?style=for-the-badge&logo=windows)](https://microsoft.com)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Local%20First-success?style=for-the-badge)](https://github.com/mahmoud-gala-dev/SnipGlide)

📖 **[اضغط هنا لقراءة الدليل الشامل والمفصل لجميع المميزات (PROJECT_FEATURES.md)](PROJECT_FEATURES.md)**

</div>

---

## 🌟 Key Highlights / أبرز المميزات

| الميزة | Description |
|---|---|
| ⚡ **Smart Text Expansion** | Background global keyboard listener that expands custom snippets (`#sig`, `$date`, etc.) with dynamic variables (`{date}`, `{time}`, `{clipboard}`) and regex support across all Windows apps. |
| 🛠️ **Developer Toolbox (Phases 1–3)** | Complete developer utilities: JSON formatter/validator, Base64, URL encoder, JWT decoder, UUID generator, Timestamp converter, Hashes (MD5/SHA), Text case utils, Regex Playground with ReDoS protection, and Smart Code Snippets with form placeholders. |
| 🌐 **REST API Tester (Phase 4)** | Lightweight, thread-isolated HTTP client supporting GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, headers/params editor, Bearer/Basic/API Key auth, response viewer, cURL export, and sanitized history/saved requests. |
| 🐙 **Git Developer Tools (Phase 5)** | Local repository status inspector, branch tracking, working/staged diff viewer with syntax coloring, commit history, and automated Conventional Commit message generation. |
| 🤖 **AI Coding Platform (Phase 6)** | Multi-provider architecture (Gemini, OpenAI, Local Ollama, OpenAI-Compatible) with token streaming, 13 coding actions (Explain, Refactor, Bugs, Tests, Docstrings, Types, Regex, SQL, Convert), and strict privacy context preview confirmation. |
| 📁 **Projects & Command Library (Phase 7)** | Local workspace manager with automatic framework detection (Django, FastAPI, Flask, React, Next.js, Vue, Docker), active project context, and safe templated terminal command library. |
| 🔍 **Unified Developer Search (Phase 8)** | Global instant search with debouncing and ranking across Snippets, Notes, Chat Notes, Clipboard, Screenshots, Saved Regexes, API Requests, Projects, and Commands with direct navigation. |
| 📸 **Instant Screen Snipping** | Full screen capture (`Ctrl+Print`) and precision area snipping (`Win+Print`) with instant zoom viewer and clipboard copy. |
| 🎥 **HD Video Screen Recorder** | Record full screen or custom cropped areas into smooth MP4 videos with mouse pointer glow, live floating widget (`REC`), and built-in video player. |
| 🗂️ **Folders & Drag & Drop** | Organize screenshots and recordings into folders (`العامة`, `العمل`, `مشاريع`, etc.) with glowing visual Drag-and-Drop item transfer. |
| 📝 **Code Notepad & Editor** | Multi-tab notepad with line numbers, code syntax highlighting, full RTL Arabic writing support, and auto-session recovery. |
| 🔒 **100% Local & Secure** | All data is stored locally in an optimized SQLite database with master PIN security, secret redaction in logs, and backup export/import. |


---

## ⌨️ Global Shortcuts / اختصارات لوحة المفاتيح

| Shortcut | Action |
|---|---|
| <kbd>Ctrl</kbd> + <kbd>PrintScreen</kbd> | التقاط وحفظ الشاشة بالكامل فوراً (Capture Full Screen) |
| <kbd>Win</kbd> + <kbd>PrintScreen</kbd> | أداة تحديد واقتصاص جزء مخصص من الشاشة (Area Snipping) |
| <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>S</kbd> | إظهار / إخفاء التطبيق من الخلفية (Toggle App Window) |
| <kbd>Ctrl</kbd> + <kbd>B</kbd> | إظهار / طي القائمة الجانبية (Toggle Sidebar Drawer) |
| <kbd>Ctrl</kbd> + <kbd>+</kbd> / <kbd>-</kbd> | تكبير / تصغير واجهة البرنامج (Zoom UI) |
| <kbd>Ctrl</kbd> + <kbd>0</kbd> | إعادة ضبط حجم الواجهة (Reset UI Scale) |

---

## 🚀 Running from Source / التشغيل من السورس كود

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/mahmoud-gala-dev/SnipGlide.git
   cd SnipGlide
   ```

2. **Activate Virtual Environment & Install Dependencies:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Launch the Application:**
   ```powershell
   python app.py
   ```

---

## 📦 Building Standalone Executable / بناء ملف EXE مستقل

To build a standalone executable that runs without Python installed:

```powershell
pyinstaller SnipGlide.spec
```
The resulting executable will be created in `dist\SnipGlide.exe`.

---

## 📚 Complete Documentation & Security Guide
 
لمطالعة الشرح التفصيلي العميق لكل ميزة وأداة ومكون برمجي في التطبيق:
👉 **[راجع وثيقة المميزات الكاملة PROJECT_FEATURES.md](PROJECT_FEATURES.md)**

لمطالعة تفاصيل الأمان، التشفير، وعزل ReDoS:
👉 **[راجع وثيقة الأمان والخصوصية SECURITY.md](SECURITY.md)**

---

<div align="center">

Made with ❤️ by [mahmoud-gala-dev](https://github.com/mahmoud-gala-dev) • Licensed under MIT

</div>
