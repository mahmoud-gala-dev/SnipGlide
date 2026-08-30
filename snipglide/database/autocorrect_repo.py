from snipglide.database.connection import get_connection

DEFAULT_CORRECTIONS = {
    # ── Arabic Common Typos & Enhancements ──
    "انشاء الله": "إن شاء الله",
    "ان شاءالله": "إن شاء الله",
    "ان شاء الله": "إن شاء الله",
    "شكراا": "شكراً",
    "شكرا جزيلا": "شكراً جزيلاً",
    "جزاك الله خير": "جزاك الله خيراً",
    "السلام عليكم ورحمة الله": "السلام عليكم ورحمة الله وبركاته",
    "مساء الخيؤ": "مساء الخير",
    "صباح الخيؤ": "صباح الخير",
    "اللة": "الله",
    "ايضا": "أيضاً",
    "مرحباا": "مرحباً",
    "بالتاكيد": "بالتأكيد",
    "هاذا": "هذا",
    "هذة": "هذه",
    "مسؤل": "مسؤول",
    "شئ": "شيء",
    "شكرن": "شكراً",
    "عفون": "عفواً",
    "اهلن": "أهلاً",
    "سهلن": "سهلاً",

    # ── English Common Typos ──
    "teh": "the",
    "recieve": "receive",
    "seperate": "separate",
    "adress": "address",
    "dont": "don't",
    "cant": "can't",
    "wont": "won't",
    "didnt": "didn't",
    "isnt": "isn't",
    "definitly": "definitely",
    "occured": "occurred",
    "untill": "until",
    "truely": "truly",
    "goverment": "government",
    "enviroment": "environment",
    "begining": "beginning",
    "alot": "a lot",
    "accomodate": "accommodate",
    "appologize": "apologize",
    "thier": "their",
    "beleive": "believe",
    "calender": "calendar",
    "neccessary": "necessary",
}

def get_all_corrections() -> dict[str, str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT typo, correction FROM autocorrect")
        rows = cursor.fetchall()
        if not rows:
            seed_default_autocorrect()
            cursor.execute("SELECT typo, correction FROM autocorrect")
            rows = cursor.fetchall()
        return {row["typo"]: row["correction"] for row in rows}

def seed_default_autocorrect():
    with get_connection() as conn:
        cursor = conn.cursor()
        for typo, correction in DEFAULT_CORRECTIONS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO autocorrect (typo, correction) VALUES (?, ?)",
                (typo.strip().lower(), correction.strip())
            )
        conn.commit()

def add_autocorrect(typo: str, correction: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO autocorrect (typo, correction) VALUES (?, ?)",
            (typo.strip().lower(), correction.strip())
        )
        conn.commit()

def delete_autocorrect(typo: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM autocorrect WHERE typo = ?", (typo.strip().lower(),))
        conn.commit()
