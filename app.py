
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray
from pynput import keyboard


APP_NAME = "SnipGlide Python"
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "SnipGlidePython"
DATA_FILE = DATA_DIR / "snippets.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative


class SnippetStore:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.snippets: List[Dict] = []
        self.settings = {
            "enabled": True,
            "start_minimized": False,
            "case_sensitive": True,
            "max_buffer": 250,
        }
        self.load()

    def load(self):
        with self._lock:
            if DATA_FILE.exists():
                try:
                    self.snippets = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                except Exception:
                    self.snippets = []
            if SETTINGS_FILE.exists():
                try:
                    loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                    self.settings.update(loaded)
                except Exception:
                    pass

    def save(self):
        with self._lock:
            DATA_FILE.write_text(
                json.dumps(self.snippets, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            SETTINGS_FILE.write_text(
                json.dumps(self.settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def add(self, trigger: str, replacement: str, enabled: bool = True):
        trigger = trigger.strip()
        if not trigger:
            raise ValueError("الاختصار لا يمكن أن يكون فارغًا.")
        with self._lock:
            if any(item["trigger"] == trigger for item in self.snippets):
                raise ValueError("هذا الاختصار موجود بالفعل.")
            self.snippets.append({
                "trigger": trigger,
                "replacement": replacement,
                "enabled": enabled,
            })
            self.save()

    def update(self, index: int, trigger: str, replacement: str, enabled: bool):
        trigger = trigger.strip()
        if not trigger:
            raise ValueError("الاختصار لا يمكن أن يكون فارغًا.")
        with self._lock:
            for i, item in enumerate(self.snippets):
                if i != index and item["trigger"] == trigger:
                    raise ValueError("هذا الاختصار موجود بالفعل.")
            self.snippets[index] = {
                "trigger": trigger,
                "replacement": replacement,
                "enabled": enabled,
            }
            self.save()

    def delete(self, index: int):
        with self._lock:
            del self.snippets[index]
            self.save()

    def active_map(self) -> Dict[str, str]:
        with self._lock:
            return {
                item["trigger"]: item["replacement"]
                for item in self.snippets
                if item.get("enabled", True)
            }


class ExpansionEngine:
    def __init__(self, store: SnippetStore, status_callback=None):
        self.store = store
        self.status_callback = status_callback
        self.buffer = ""
        self.controller = keyboard.Controller()
        self.listener: Optional[keyboard.Listener] = None
        self.running = False
        self.suspended = False
        self._lock = threading.RLock()

    def start(self):
        if self.listener is not None:
            return
        self.running = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.daemon = True
        self.listener.start()
        self._notify()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        self._notify()

    def set_suspended(self, value: bool):
        self.suspended = value
        self.buffer = ""
        self._notify()

    def _notify(self):
        if self.status_callback:
            try:
                self.status_callback(self.running and not self.suspended)
            except Exception:
                pass

    def _on_press(self, key):
        if not self.running or self.suspended or not self.store.settings.get("enabled", True):
            return

        try:
            if key == keyboard.Key.backspace:
                self.buffer = self.buffer[:-1]
                return

            if key in {
                keyboard.Key.space, keyboard.Key.enter, keyboard.Key.tab,
                keyboard.Key.esc, keyboard.Key.left, keyboard.Key.right,
                keyboard.Key.up, keyboard.Key.down, keyboard.Key.home,
                keyboard.Key.end, keyboard.Key.page_up, keyboard.Key.page_down,
                keyboard.Key.delete,
            }:
                self.buffer = ""
                return

            char = getattr(key, "char", None)
            if char is None:
                return

            self.buffer += char
            max_len = int(self.store.settings.get("max_buffer", 250))
            self.buffer = self.buffer[-max_len:]

            snippets = self.store.active_map()
            case_sensitive = self.store.settings.get("case_sensitive", True)

            matched_trigger = None
            replacement = None

            for trigger, repl in sorted(snippets.items(), key=lambda x: len(x[0]), reverse=True):
                if case_sensitive:
                    matched = self.buffer.endswith(trigger)
                else:
                    matched = self.buffer.lower().endswith(trigger.lower())
                if matched:
                    matched_trigger = trigger
                    replacement = repl
                    break

            if matched_trigger is not None:
                self._expand(matched_trigger, replacement)

        except Exception:
            self.buffer = ""

    def _expand(self, trigger: str, replacement: str):
        with self._lock:
            self.suspended = True
            try:
                for _ in trigger:
                    self.controller.press(keyboard.Key.backspace)
                    self.controller.release(keyboard.Key.backspace)
                    time.sleep(0.002)

                self.controller.type(replacement)
                self.buffer = ""
            finally:
                time.sleep(0.03)
                self.suspended = False


class SnipGlideApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.store = SnippetStore()
        self.engine = ExpansionEngine(self.store, self._engine_status_changed)
        self.selected_index: Optional[int] = None
        self.tray_icon = None

        self.title(APP_NAME)
        self.geometry("980x650")
        self.minsize(850, 560)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self._build_ui()
        self._refresh_list()
        self.engine.start()
        self._start_tray()

        if self.store.settings.get("start_minimized", False):
            self.after(200, self.hide_window)

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="SnipGlide",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            sidebar,
            text="اختصاراتك، بطريقتك",
            text_color=("gray35", "gray70"),
        ).pack(pady=(0, 22))

        self.status_label = ctk.CTkLabel(
            sidebar,
            text="● يعمل في الخلفية",
            text_color="#22c55e",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.status_label.pack(pady=8)

        self.enable_switch = ctk.CTkSwitch(
            sidebar,
            text="تفعيل الاستبدال",
            command=self._toggle_enabled,
        )
        self.enable_switch.pack(pady=12)
        if self.store.settings.get("enabled", True):
            self.enable_switch.select()

        self.case_switch = ctk.CTkSwitch(
            sidebar,
            text="حسّاس لحالة الأحرف",
            command=self._toggle_case,
        )
        self.case_switch.pack(pady=12)
        if self.store.settings.get("case_sensitive", True):
            self.case_switch.select()

        self.min_switch = ctk.CTkSwitch(
            sidebar,
            text="البدء مصغّرًا",
            command=self._toggle_start_minimized,
        )
        self.min_switch.pack(pady=12)
        if self.store.settings.get("start_minimized", False):
            self.min_switch.select()

        ctk.CTkButton(
            sidebar,
            text="إضافة اختصار جديد",
            height=42,
            command=self._new_snippet,
        ).pack(fill="x", padx=24, pady=(28, 10))

        ctk.CTkButton(
            sidebar,
            text="إخفاء إلى جوار الساعة",
            fg_color="transparent",
            border_width=1,
            command=self.hide_window,
        ).pack(fill="x", padx=24, pady=8)

        ctk.CTkLabel(
            sidebar,
            text="يقبل أي نص أو رموز:\n! @ # $ % ^ & * ( ) _ +",
            justify="center",
            text_color=("gray40", "gray65"),
        ).pack(side="bottom", pady=24)

        main = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray96", "gray10"))
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="إدارة الاختصارات",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.search_entry = ctk.CTkEntry(
            header,
            width=260,
            placeholder_text="ابحث عن اختصار...",
        )
        self.search_entry.grid(row=0, column=1, sticky="e")
        self.search_entry.bind("<KeyRelease>", lambda _e: self._refresh_list())

        content = ctk.CTkFrame(main)
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 28))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        self.list_frame = ctk.CTkScrollableFrame(content, label_text="الاختصارات")
        self.list_frame.grid(row=0, column=0, sticky="nsew", padx=(14, 7), pady=14)

        editor = ctk.CTkFrame(content)
        editor.grid(row=0, column=1, sticky="nsew", padx=(7, 14), pady=14)
        editor.grid_columnconfigure(0, weight=1)
        editor.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            editor,
            text="محرر الاختصار",
            font=ctk.CTkFont(size=19, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 12))

        ctk.CTkLabel(editor, text="الاختصار").grid(
            row=1, column=0, sticky="w", padx=20, pady=(4, 4)
        )
        self.trigger_entry = ctk.CTkEntry(
            editor,
            placeholder_text='مثال: #عنوان أو $توقيع أو !@#',
            height=40,
        )
        self.trigger_entry.grid(row=2, column=0, sticky="ew", padx=20)

        ctk.CTkLabel(editor, text="النص البديل").grid(
            row=3, column=0, sticky="w", padx=20, pady=(16, 4)
        )
        self.replacement_text = ctk.CTkTextbox(editor, wrap="word")
        self.replacement_text.grid(row=4, column=0, sticky="nsew", padx=20)

        self.item_enabled = ctk.CTkCheckBox(editor, text="هذا الاختصار مفعّل")
        self.item_enabled.grid(row=5, column=0, sticky="w", padx=20, pady=14)
        self.item_enabled.select()

        buttons = ctk.CTkFrame(editor, fg_color="transparent")
        buttons.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 20))
        buttons.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            buttons, text="حفظ", command=self._save_snippet
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            buttons,
            text="جديد",
            fg_color=("gray70", "gray30"),
            command=self._new_snippet,
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ctk.CTkButton(
            buttons,
            text="حذف",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=self._delete_snippet,
        ).grid(row=0, column=2, sticky="ew", padx=(5, 0))

    def _refresh_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        query = self.search_entry.get().strip().lower() if hasattr(self, "search_entry") else ""
        visible = []
        for i, item in enumerate(self.store.snippets):
            text = f'{item["trigger"]} {item["replacement"]}'.lower()
            if not query or query in text:
                visible.append((i, item))

        if not visible:
            ctk.CTkLabel(
                self.list_frame,
                text="لا توجد اختصارات بعد.\nأضف أول اختصار الآن.",
                text_color=("gray40", "gray65"),
            ).pack(pady=35)
            return

        for index, item in visible:
            preview = item["replacement"].replace("\n", " ")
            if len(preview) > 45:
                preview = preview[:45] + "…"

            button = ctk.CTkButton(
                self.list_frame,
                text=f'{item["trigger"]}\n{preview}',
                anchor="w",
                height=62,
                fg_color=("gray88", "gray18"),
                hover_color=("gray80", "gray25"),
                text_color=("gray10", "gray95"),
                command=lambda idx=index: self._select_snippet(idx),
            )
            button.pack(fill="x", pady=5)

    def _select_snippet(self, index: int):
        self.selected_index = index
        item = self.store.snippets[index]
        self.trigger_entry.delete(0, "end")
        self.trigger_entry.insert(0, item["trigger"])
        self.replacement_text.delete("1.0", "end")
        self.replacement_text.insert("1.0", item["replacement"])
        if item.get("enabled", True):
            self.item_enabled.select()
        else:
            self.item_enabled.deselect()

    def _new_snippet(self):
        self.selected_index = None
        self.trigger_entry.delete(0, "end")
        self.replacement_text.delete("1.0", "end")
        self.item_enabled.select()
        self.trigger_entry.focus_set()

    def _save_snippet(self):
        trigger = self.trigger_entry.get()
        replacement = self.replacement_text.get("1.0", "end-1c")
        enabled = bool(self.item_enabled.get())

        try:
            if self.selected_index is None:
                self.store.add(trigger, replacement, enabled)
                self.selected_index = len(self.store.snippets) - 1
            else:
                self.store.update(self.selected_index, trigger, replacement, enabled)
            self._refresh_list()
            self._toast("تم حفظ الاختصار بنجاح")
        except ValueError as exc:
            self._toast(str(exc), error=True)

    def _delete_snippet(self):
        if self.selected_index is None:
            self._toast("اختر اختصارًا أولًا", error=True)
            return
        self.store.delete(self.selected_index)
        self._new_snippet()
        self._refresh_list()
        self._toast("تم حذف الاختصار")

    def _toggle_enabled(self):
        self.store.settings["enabled"] = bool(self.enable_switch.get())
        self.store.save()
        self.engine.set_suspended(not self.store.settings["enabled"])

    def _toggle_case(self):
        self.store.settings["case_sensitive"] = bool(self.case_switch.get())
        self.store.save()

    def _toggle_start_minimized(self):
        self.store.settings["start_minimized"] = bool(self.min_switch.get())
        self.store.save()

    def _engine_status_changed(self, active: bool):
        def update():
            if active and self.store.settings.get("enabled", True):
                self.status_label.configure(text="● يعمل في الخلفية", text_color="#22c55e")
            else:
                self.status_label.configure(text="● متوقف مؤقتًا", text_color="#f59e0b")
        try:
            self.after(0, update)
        except Exception:
            pass

    def _toast(self, message: str, error: bool = False):
        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        color = "#dc2626" if error else "#16a34a"
        label = ctk.CTkLabel(
            popup,
            text=message,
            fg_color=color,
            text_color="white",
            corner_radius=10,
            padx=18,
            pady=10,
        )
        label.pack()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() - 330
        y = self.winfo_y() + 35
        popup.geometry(f"+{x}+{y}")
        popup.after(1800, popup.destroy)

    def hide_window(self):
        self.withdraw()

    def show_window(self):
        self.after(0, self.deiconify)
        self.after(20, self.lift)
        self.after(30, self.focus_force)

    def _create_tray_image(self):
        image = Image.new("RGB", (64, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=15, fill=(37, 99, 235))
        draw.text((21, 14), "S", fill="white")
        return image

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("فتح SnipGlide", lambda: self.show_window(), default=True),
            pystray.MenuItem(
                "تفعيل / إيقاف",
                lambda: self.after(0, self._tray_toggle),
            ),
            pystray.MenuItem("خروج", lambda: self.after(0, self._quit_app)),
        )
        self.tray_icon = pystray.Icon(
            "SnipGlidePython",
            self._create_tray_image(),
            APP_NAME,
            menu,
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_toggle(self):
        if self.enable_switch.get():
            self.enable_switch.deselect()
        else:
            self.enable_switch.select()
        self._toggle_enabled()

    def _quit_app(self):
        self.engine.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()


if __name__ == "__main__":
    app = SnipGlideApp()
    app.mainloop()
