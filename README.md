# SnipGlide Python

A background text snippet expansion application for Windows.

## Features

- **Categorize Snippets**: Group snippets into custom groups (e.g. Work, Personal) and filter them in the list.
- **Excel Support**: Import shortcuts directly from Excel (`.xlsx`) files or download a formatted template to quickly structure your shortcuts.
- **English UI**: The entire user interface, alerts, and settings are fully localized in English.
- **Flexible Triggers**: Accepts any custom text or symbol sequence, such as:
  - `#sig`
  - `$date`
  - `!@#$`
  - `hello`
- No trailing colons or fixed prefixes required.
- Modern look and feel supporting Light and Dark modes.
- Runs silently in the background with a system tray icon.
- Show or hide the app from the background with `Ctrl+Alt+Shift+S`.
- Zoom the app UI with the toolbar buttons or `Ctrl++`, `Ctrl+-`, and `Ctrl+0`.
- Notes section with categories, pinned notes, quick search, and one-click copy.
- Notes editor supports Arabic RTL writing, font size, line spacing, and stores notes-page preferences in SQLite.
- Clicking a note copies its content to the clipboard immediately.
- Clipboard history keeps the latest 50 entries only, shown as 5 pages with 10 entries per page.
- Toggle individual snippets on/off dynamically.
- Quick real-time search.
- Local automatic persistence: data is saved locally on your device under `%APPDATA%\SnipGlidePython` (it never leaves your machine).

## Running from Source

1. Install Python 3.11 or newer.
2. Open PowerShell or Command Prompt inside the project directory.
3. Execute:

```powershell
# Installs requirements in the environment
pip install -r requirements.txt

# Runs the application
python app.py
```

*Note: You can also use `run.bat` to automatically build/run the virtual environment and install requirements.*

## Building Standalone Executable

To compile SnipGlide into a standalone `.exe` file, run:

```powershell
build_exe.bat
```

The resulting executable will be available under:

```text
dist\SnipGlide.exe
```

## Running at Windows Startup

After building the EXE file:
1. Press `Win + R` to open the Run dialog.
2. Type `shell:startup` and press Enter.
3. Place a shortcut to `SnipGlide.exe` inside the opened Startup folder.

## Notes & Best Practices

- This application is optimized for Windows.
- Some programs running as Administrator might block keystroke insertion unless SnipGlide is also running with Administrator privileges.
- To prevent unintended text expansions, use unique prefixes or symbols (e.g., `#sig` or `@@addr`) for triggers.
