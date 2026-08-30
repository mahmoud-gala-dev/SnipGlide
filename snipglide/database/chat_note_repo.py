import sqlite3
from typing import List, Optional
from datetime import datetime
from snipglide.database.connection import get_connection
from snipglide.models.chat_note import ChatNote, ChatNoteSection


def get_all_chat_sections() -> List[ChatNoteSection]:
    """Retrieve all chat note sections/categories."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon, color FROM chat_note_sections ORDER BY id ASC")
        rows = cursor.fetchall()
        return [
            ChatNoteSection(
                id=row["id"],
                name=row["name"],
                icon=row["icon"] or "💬",
                color=row["color"] or "#25D366",
            )
            for row in rows
        ]


def add_chat_section(name: str, icon: str = "💬", color: str = "#25D366") -> ChatNoteSection:
    name = name.strip()
    if not name:
        raise ValueError("Section name cannot be empty.")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_note_sections (name, icon, color) VALUES (?, ?, ?)",
            (name, icon or "💬", color or "#25D366"),
        )
        conn.commit()
        sec_id = cursor.lastrowid
        return ChatNoteSection(id=sec_id, name=name, icon=icon, color=color)


def delete_chat_section(section_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_note_sections WHERE id = ?", (section_id,))
        # Re-assign orphan notes to default section 1
        cursor.execute("UPDATE chat_notes SET section_id = 1 WHERE section_id = ?", (section_id,))
        conn.commit()


def get_all_chat_notes(
    query: str = "",
    starred_only: bool = False,
    section_id: Optional[int] = None,
    limit: int = 500,
) -> List[ChatNote]:
    """Retrieve chat notes ordered chronologically."""
    clauses = []
    params = []

    if starred_only:
        clauses.append("is_starred = 1")

    if section_id is not None and section_id > 0:
        clauses.append("section_id = ?")
        params.append(section_id)

    if query.strip():
        term = f"%{query.strip()}%"
        clauses.append("content LIKE ?")
        params.append(term)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, content, created_at, is_starred, section_id, tags, color
            FROM (
                SELECT id, content, created_at, is_starred, section_id, tags, color
                FROM chat_notes
                {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            )
            ORDER BY created_at ASC, id ASC
            """,
            params,
        )
        rows = cursor.fetchall()
        return [
            ChatNote(
                id=row["id"],
                content=row["content"],
                created_at=row["created_at"],
                is_starred=bool(row["is_starred"]),
                section_id=row["section_id"] if row["section_id"] is not None else 1,
                tags=row["tags"] or "",
                color=row["color"] or "#25D366",
            )
            for row in rows
        ]


def get_chat_note_by_id(note_id: int) -> Optional[ChatNote]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content, created_at, is_starred, section_id, tags, color FROM chat_notes WHERE id = ?",
            (note_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ChatNote(
            id=row["id"],
            content=row["content"],
            created_at=row["created_at"],
            is_starred=bool(row["is_starred"]),
            section_id=row["section_id"] if row["section_id"] is not None else 1,
            tags=row["tags"] or "",
            color=row["color"] or "#25D366",
        )


def add_chat_note(
    content: str,
    is_starred: bool = False,
    section_id: int = 1,
    tags: str = "",
    color: str = "#25D366",
) -> ChatNote:
    if not content.strip():
        raise ValueError("Chat note content cannot be empty.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_notes (content, created_at, is_starred, section_id, tags, color)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (content.strip(), now_str, 1 if is_starred else 0, section_id, tags, color),
        )
        conn.commit()
        note_id = cursor.lastrowid
        return ChatNote(
            id=note_id,
            content=content.strip(),
            created_at=now_str,
            is_starred=is_starred,
            section_id=section_id,
            tags=tags,
            color=color,
        )


def delete_chat_note(note_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_notes WHERE id = ?", (note_id,))
        conn.commit()


def toggle_star_chat_note(note_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_starred FROM chat_notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if row["is_starred"] else 1
        cursor.execute("UPDATE chat_notes SET is_starred = ? WHERE id = ?", (new_val, note_id))
        conn.commit()
        return bool(new_val)


def update_chat_note_content(note_id: int, new_content: str):
    if not new_content.strip():
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_notes SET content = ? WHERE id = ?", (new_content.strip(), note_id))
        conn.commit()


def clear_all_chat_notes(section_id: Optional[int] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if section_id and section_id > 0:
            cursor.execute("DELETE FROM chat_notes WHERE section_id = ?", (section_id,))
        else:
            cursor.execute("DELETE FROM chat_notes")
        conn.commit()


def get_chat_notes_count(starred_only: bool = False, section_id: Optional[int] = None) -> int:
    clauses = []
    params = []
    if starred_only:
        clauses.append("is_starred = 1")
    if section_id and section_id > 0:
        clauses.append("section_id = ?")
        params.append(section_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM chat_notes {where_sql}", params)
        return cursor.fetchone()[0]


def seed_demo_chat_notes():
    """Populate realistic sample chat notes across sections to showcase the design."""
    sections = get_all_chat_sections()
    sec_map = {s.name: s.id for s in sections}

    demo_notes = [
        # عام (General)
        ("مرحباً بك في شات الملاحظات السريعة! 🎉\nيمكنك هنا كتابة أفكارك ومقتطفاتك اليومية بأسلوب محادثات الواتساب الأنيق والسلس.", False, sec_map.get("عام", 1)),
        ("🎙️ [ملاحظة صوتية - Voice Note (00:05)]\n▶️  ▂▃▅▇▅▃▂ ▃▅▇▅  (5 ثانية)", False, sec_map.get("عام", 1)),
        ("💡 فكرة: تحويل الملاحظة المهمة إلى اختصار دائم عبر زر (✂️ اختصار) بضغطة زر واحدة!", True, sec_map.get("عام", 1)),
        # أفكار ومشاريع (Ideas)
        ("🚀 ميزة مقترحة للإصدار القادم:\n- دعم التزامن السحابي المباشر عبر Google Drive / Dropbox\n- إضافة قوالب ذكية للردود التلقائية", True, sec_map.get("أفكار ومشاريع", 2)),
        ("🎨 تجربة تصميم لوحة إحصائيات تفاعلية تعرض الكلمات الموفرة يومياً.", False, sec_map.get("أفكار ومشاريع", 2)),
        # مهام سريعة (Tasks)
        ("✅ قائمة المهام اليومية:\n1. مراجعة كود اختصارات بايثون\n2. تجربة خط تجوال مع النصوص العربية\n3. تنزيل حزمة الاختصارات من المتجر", False, sec_map.get("مهام سريعة", 3)),
        ("⏰ تذكير: الاتصال بفريق الدعم الفني وتحديث إعدادات النسخ الاحتياطي.", True, sec_map.get("مهام سريعة", 3)),
        # روابط ومعلومات (Links & Info)
        ("🔗 رابط مكتبة الخطوط العربية من جوجل:\nhttps://fonts.google.com/?subset=arabic", False, sec_map.get("روابط ومعلومات", 4)),
        ("📚 مرجع مفيد لأوامر الاختصارات: {{date}}, {{time}}, {{clipboard}}, {{form:Field}}", True, sec_map.get("روابط ومعلومات", 4)),
        # ملاحظات عمل (Work)
        ("💼 اجتماع الغد الساعة 10:00 صباحاً لمناقشة تسريع أداء محرر النصوص وقواعد البيانات.", False, sec_map.get("ملاحظات عمل", 5)),
        ("📌 قالب إيميل رسمي معتمد:\nالسلام عليكم ورحمة الله،\nتحية طيبة وبعد،\nيسعدنا تواصلكم ونفيدكم باكتمال الطلب بنجاح.", True, sec_map.get("ملاحظات عمل", 5)),
    ]

    for content, is_starred, s_id in demo_notes:
        add_chat_note(content=content, is_starred=is_starred, section_id=s_id)
