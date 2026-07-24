from snipglide.database.connection import get_connection

def get_all_corrections() -> dict[str, str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT typo, correction FROM autocorrect")
        return {row["typo"]: row["correction"] for row in cursor.fetchall()}

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
