import sqlite3
from snipglide.core.config import DB_FILE

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    with get_connection() as conn:
        cursor = conn.cursor()
        
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

        # Store lightweight UI preferences for the notes page in the database.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        conn.commit()
