import sqlite3
from snipglide.core.config import DB_FILE

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -32000")
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


def initialize_database():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        
        # Create groups table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT 'G',
                color TEXT DEFAULT '#2563eb',
                description TEXT DEFAULT '',
                is_collapsed INTEGER DEFAULT 0
            )
        """)
        
        # Insert default General group if it doesn't exist
        cursor.execute("SELECT id FROM groups WHERE name = 'General'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO groups (name, icon, color) VALUES ('General', 'G', '#2563eb')")
            
        # Create snippets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shortcut TEXT NOT NULL UNIQUE,
                replacement TEXT NOT NULL,
                group_id INTEGER,
                tags TEXT DEFAULT '',
                description TEXT DEFAULT '',
                language TEXT DEFAULT 'Plain Text',
                enabled INTEGER DEFAULT 1,
                favorite INTEGER DEFAULT 0,
                usage_counter INTEGER DEFAULT 0,
                created_date TEXT,
                modified_date TEXT,
                hotkey TEXT DEFAULT '',
                regex_enabled INTEGER DEFAULT 0,
                app_filter TEXT DEFAULT '',
                window_filter TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
            )
        """)
        
        # Build indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippets_shortcut ON snippets (shortcut)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippets_group_id ON snippets (group_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippets_favorite ON snippets (favorite)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippets_modified ON snippets (modified_date)")
        
        # Create autocorrect table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autocorrect (
                typo TEXT PRIMARY KEY,
                correction TEXT NOT NULL
            )
        """)
        
        # Prepopulate autocorrect if empty
        cursor.execute("SELECT COUNT(*) FROM autocorrect")
        if cursor.fetchone()[0] == 0:
            default_corrections = [
                ("teh", "the"),
                ("recieve", "receive"),
                ("seperate", "separate"),
                ("wierd", "weird"),
                ("dont", "don't"),
                ("cant", "can't"),
                ("wont", "won't"),
                ("shoudl", "should"),
                ("becuase", "because"),
                ("definately", "definitely")
            ]
            cursor.executemany("INSERT INTO autocorrect (typo, correction) VALUES (?, ?)", default_corrections)
            
        # Create clipboard history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT UNIQUE NOT NULL,
                copied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clipboard_history_copied ON clipboard_history (copied_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clipboard_history_page ON clipboard_history (copied_at DESC, id DESC)")
        cursor.execute("""
            DELETE FROM clipboard_history
            WHERE id NOT IN (
                SELECT id FROM clipboard_history
                ORDER BY copied_at DESC, id DESC
                LIMIT 50
            )
        """)
        
        # Create usage history table for analytics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snippet_id INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_history_used ON usage_history (used_at)")
        cursor.execute("DELETE FROM usage_history WHERE used_at < date('now', '-365 days')")
        
        # Create note categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT 'N',
                color TEXT DEFAULT '#2563eb',
                description TEXT DEFAULT ''
            )
        """)
        
        # Insert default note category
        cursor.execute("SELECT id FROM note_categories WHERE name = 'General'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO note_categories (name, icon, color) VALUES ('General', 'N', '#2563eb')")
        
        # Create notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category_id INTEGER,
                created_date TEXT,
                modified_date TEXT,
                color TEXT DEFAULT '#2563eb',
                pinned INTEGER DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES note_categories(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_category ON notes (category_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes (pinned)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_modified ON notes (modified_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_title ON notes (title)")

        # Store lightweight UI preferences for the notes page in the database.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Create chat note sections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_note_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT '💬',
                color TEXT DEFAULT '#25D366'
            )
        """)
        
        # Prepopulate default chat sections if empty
        cursor.execute("SELECT COUNT(*) FROM chat_note_sections")
        if cursor.fetchone()[0] == 0:
            default_sections = [
                ("عام", "💬", "#25D366"),
                ("أفكار ومشاريع", "💡", "#f59e0b"),
                ("مهام سريعة", "⚡", "#3b82f6"),
                ("روابط ومعلومات", "🔗", "#8b5cf6"),
                ("ملاحظات عمل", "💼", "#0f766e"),
            ]
            cursor.executemany("INSERT INTO chat_note_sections (name, icon, color) VALUES (?, ?, ?)", default_sections)

        # Create quick chat notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_starred INTEGER DEFAULT 0,
                section_id INTEGER DEFAULT 1,
                tags TEXT DEFAULT '',
                color TEXT DEFAULT '#25D366',
                FOREIGN KEY (section_id) REFERENCES chat_note_sections(id) ON DELETE SET NULL
            )
        """)
        
        # Migration: ensure section_id exists if table already existed
        cursor.execute("PRAGMA table_info(chat_notes)")
        columns = [col[1] for col in cursor.fetchall()]
        if "section_id" not in columns:
            cursor.execute("ALTER TABLE chat_notes ADD COLUMN section_id INTEGER DEFAULT 1")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_notes_created ON chat_notes (created_at DESC, id DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_notes_starred ON chat_notes (is_starred)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_notes_section ON chat_notes (section_id)")
        
        # Create screenshots & recordings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                capture_type TEXT DEFAULT 'full',
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_favorite INTEGER DEFAULT 0,
                note TEXT DEFAULT '',
                duration REAL DEFAULT 0.0,
                thumbnail_path TEXT DEFAULT '',
                folder TEXT DEFAULT 'العامة'
            )
        """)

        # Migration: ensure duration, thumbnail_path, and folder exist if table already existed
        cursor.execute("PRAGMA table_info(screenshots)")
        shot_columns = [col[1] for col in cursor.fetchall()]
        if "duration" not in shot_columns:
            cursor.execute("ALTER TABLE screenshots ADD COLUMN duration REAL DEFAULT 0.0")
        if "thumbnail_path" not in shot_columns:
            cursor.execute("ALTER TABLE screenshots ADD COLUMN thumbnail_path TEXT DEFAULT ''")
        if "folder" not in shot_columns:
            cursor.execute("ALTER TABLE screenshots ADD COLUMN folder TEXT DEFAULT 'العامة'")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_created ON screenshots (created_at DESC, id DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_favorite ON screenshots (is_favorite)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_type ON screenshots (capture_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_folder ON screenshots (folder)")

        # Create screenshot folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screenshot_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#3b82f6',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM screenshot_folders")
        if cursor.fetchone()[0] == 0:
            default_flds = [
                ("العامة", "#3b82f6"),
                ("العمل", "#10b981"),
                ("مشاريع", "#f59e0b"),
                ("شروحات", "#8b5cf6")
            ]
            cursor.executemany("INSERT INTO screenshot_folders (name, color) VALUES (?, ?)", default_flds)

        conn.commit()

