import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Tuple

from snipglide.database.snippet_repo import get_all_snippets, add_snippet
from snipglide.database.note_repo import get_all_notes, add_note
from snipglide.database.chat_note_repo import get_all_chat_notes, add_chat_note
from snipglide.models.snippet import Snippet
from snipglide.models.note import Note

def export_data_to_json(file_path: str) -> Tuple[bool, str]:
    try:
        snippets = get_all_snippets()
        notes = get_all_notes()
        chat_notes = get_all_chat_notes()

        data = {
            "exported_at": datetime.now().isoformat(),
            "version": "2.0",
            "snippets": [
                {
                    "shortcut": s.shortcut,
                    "replacement": s.replacement,
                    "description": s.description,
                    "tags": s.tags,
                    "group_id": s.group_id,
                }
                for s in snippets
            ],
            "notes": [
                {
                    "title": n.title,
                    "content": n.content,
                    "pinned": n.pinned,
                    "created_date": n.created_date,
                }
                for n in notes
            ],
            "chat_notes": [
                {
                    "content": c.content,
                    "is_starred": c.is_starred,
                    "section_id": c.section_id,
                    "created_at": c.created_at,
                }
                for c in chat_notes
            ],
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True, f"تم تصدير {len(snippets)} اختصار و {len(notes)} ملاحظة و {len(chat_notes)} رسالة شات بنجاح!"
    except Exception as e:
        return False, f"فشل التصدير: {e}"

def import_data_from_json(file_path: str) -> Tuple[bool, str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        snip_count = 0
        for s_data in data.get("snippets", []):
            sc = s_data.get("shortcut", "").strip()
            rep = s_data.get("replacement", "").strip()
            if sc and rep:
                snip = Snippet(
                    shortcut=sc,
                    replacement=rep,
                    description=s_data.get("description", ""),
                    tags=s_data.get("tags", []),
                )
                try:
                    add_snippet(snip)
                    snip_count += 1
                except Exception:
                    pass

        note_count = 0
        for n_data in data.get("notes", []):
            title = n_data.get("title", "").strip()
            content = n_data.get("content", "")
            if title:
                note = Note(
                    title=title,
                    content=content,
                    pinned=bool(n_data.get("pinned", False)),
                )
                try:
                    add_note(note)
                    note_count += 1
                except Exception:
                    pass

        chat_count = 0
        for c_data in data.get("chat_notes", []):
            content = c_data.get("content", "").strip()
            if content:
                try:
                    add_chat_note(
                        content=content,
                        is_starred=bool(c_data.get("is_starred", False)),
                        section_id=c_data.get("section_id", 1),
                    )
                    chat_count += 1
                except Exception:
                    pass

        return True, f"تم استيراد {snip_count} اختصار و {note_count} ملاحظة و {chat_count} رسالة بنجاح! 🎉"
    except Exception as e:
        return False, f"فشل الاستيراد: {e}"

def export_snippets_to_csv(file_path: str) -> Tuple[bool, str]:
    try:
        snippets = get_all_snippets()
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["shortcut", "replacement", "description"])
            for s in snippets:
                writer.writerow([s.shortcut, s.replacement, s.description])
        return True, f"تم تصدير {len(snippets)} اختصار إلى ملف CSV بنجاح!"
    except Exception as e:
        return False, f"فشل التصدير: {e}"
