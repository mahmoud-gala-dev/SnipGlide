import json
from datetime import datetime
from typing import Optional
from snipglide.database.connection import get_connection
from snipglide.models.api_request import ApiRequest, ApiHistoryEntry
from snipglide.services.security import encrypt_secret, decrypt_secret, sanitize_url_query
from snipglide.utils.logger import logger


class ApiRepository:
    """Repository for managing saved API requests and execution history."""

    @staticmethod
    def _encrypt_auth_data(auth_data: dict) -> dict:
        if not auth_data:
            return {}
        res = dict(auth_data)
        for k in ("token", "password", "value", "secret"):
            if k in res and isinstance(res[k], str) and res[k]:
                res[k] = encrypt_secret(res[k])
        return res

    @staticmethod
    def _decrypt_auth_data(auth_data: dict) -> dict:
        if not auth_data:
            return {}
        res = dict(auth_data)
        for k in ("token", "password", "value", "secret"):
            if k in res and isinstance(res[k], str) and res[k]:
                res[k] = decrypt_secret(res[k])
        return res

    @staticmethod
    def _row_to_request(row) -> ApiRequest:
        def _safe_json(val, default):
            if not val:
                return default
            try:
                return json.loads(val)
            except Exception:
                return default

        created = None
        if row["created_at"]:
            try:
                created = datetime.fromisoformat(str(row["created_at"]))
            except Exception:
                pass

        updated = None
        if row["updated_at"]:
            try:
                updated = datetime.fromisoformat(str(row["updated_at"]))
            except Exception:
                pass

        raw_auth_data = _safe_json(row["auth_data_json"], {})
        decrypted_auth = ApiRepository._decrypt_auth_data(raw_auth_data)

        return ApiRequest(
            id=row["id"],
            name=row["name"],
            method=row["method"],
            url=row["url"],
            params=_safe_json(row["params_json"], []),
            headers=_safe_json(row["headers_json"], []),
            auth_type=row["auth_type"] or "none",
            auth_data=decrypted_auth,
            body_type=row["body_type"] or "none",
            body_content=row["body_content"] or "",
            collection_name=row["collection_name"] or "General",
            is_favorite=bool(row["is_favorite"]),
            created_at=created,
            updated_at=updated,
        )

    @staticmethod
    def add_request(req: ApiRequest) -> int:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            secured_auth = ApiRepository._encrypt_auth_data(req.auth_data or {})
            cursor.execute("""
                INSERT INTO saved_api_requests (
                    name, method, url, params_json, headers_json,
                    auth_type, auth_data_json, body_type, body_content,
                    collection_name, is_favorite, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                req.name,
                req.method,
                req.url,
                json.dumps(req.params or []),
                json.dumps(req.headers or []),
                req.auth_type,
                json.dumps(secured_auth),
                req.body_type,
                req.body_content,
                req.collection_name or "General",
                1 if req.is_favorite else 0,
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to add saved API request: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def update_request(req: ApiRequest) -> bool:
        if not req.id:
            return False
        conn = get_connection()
        try:
            cursor = conn.cursor()
            secured_auth = ApiRepository._encrypt_auth_data(req.auth_data or {})
            cursor.execute("""
                UPDATE saved_api_requests SET
                    name = ?, method = ?, url = ?, params_json = ?, headers_json = ?,
                    auth_type = ?, auth_data_json = ?, body_type = ?, body_content = ?,
                    collection_name = ?, is_favorite = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                req.name,
                req.method,
                req.url,
                json.dumps(req.params or []),
                json.dumps(req.headers or []),
                req.auth_type,
                json.dumps(secured_auth),
                req.body_type,
                req.body_content,
                req.collection_name or "General",
                1 if req.is_favorite else 0,
                req.id,
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update saved API request {req.id}: {e}")
            raise
        finally:
            conn.close()


    @staticmethod
    def get_request_by_id(req_id: int) -> Optional[ApiRequest]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM saved_api_requests WHERE id = ?", (req_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ApiRepository._row_to_request(row)
        finally:
            conn.close()

    @staticmethod
    def get_all_requests(collection: Optional[str] = None, search: str = "") -> list[ApiRequest]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM saved_api_requests WHERE 1=1"
            params = []
            if collection and collection != "All":
                query += " AND collection_name = ?"
                params.append(collection)
            if search:
                query += " AND (name LIKE ? OR url LIKE ?)"
                like = f"%{search.strip()}%"
                params.extend([like, like])
            query += " ORDER BY is_favorite DESC, updated_at DESC, id DESC"
            cursor.execute(query, params)
            return [ApiRepository._row_to_request(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def delete_request(req_id: int) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM saved_api_requests WHERE id = ?", (req_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def toggle_favorite(req_id: int) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE saved_api_requests SET is_favorite = (1 - is_favorite) WHERE id = ?", (req_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def get_collections() -> list[str]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT collection_name FROM saved_api_requests WHERE collection_name IS NOT NULL ORDER BY collection_name")
            return [row[0] for row in cursor.fetchall() if row[0]]
        finally:
            conn.close()

    # ── History Operations ──

    @staticmethod
    def add_history_entry(entry: ApiHistoryEntry) -> int:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            sanitized_url = sanitize_url_query(entry.url)
            cursor.execute("""
                INSERT INTO api_history (
                    method, url, status_code, status_text, response_time_ms, response_size_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                entry.method,
                sanitized_url,
                entry.status_code,
                entry.status_text,
                entry.response_time_ms,
                entry.response_size_bytes,
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to record API history entry: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_history(limit: int = 50) -> list[ApiHistoryEntry]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_history ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
            entries = []
            for row in cursor.fetchall():
                created = None
                if row["created_at"]:
                    try:
                        created = datetime.fromisoformat(str(row["created_at"]))
                    except Exception:
                        pass
                entries.append(ApiHistoryEntry(
                    id=row["id"],
                    method=row["method"],
                    url=row["url"],
                    status_code=row["status_code"],
                    status_text=row["status_text"] or "",
                    response_time_ms=row["response_time_ms"] or 0.0,
                    response_size_bytes=row["response_size_bytes"] or 0,
                    created_at=created,
                ))
            return entries
        finally:
            conn.close()

    @staticmethod
    def clear_history() -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM api_history")
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def delete_history_entry(entry_id: int) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM api_history WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
