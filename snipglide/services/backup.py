import json
import sqlite3
import openpyxl
import yaml
from snipglide.database.connection import get_connection
from snipglide.database.snippet_repo import add_snippet, get_snippet_by_shortcut
from snipglide.database.group_repo import get_all_groups, add_group
from snipglide.models.snippet import Snippet
from snipglide.models.group import Group
from snipglide.utils.logger import logger

def export_backup(file_path: str) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM groups")
            groups = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM snippets")
            snippets = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM autocorrect")
            autocorrect = [dict(row) for row in cursor.fetchall()]
            
            backup_data = {
                "version": "1.0",
                "groups": groups,
                "snippets": snippets,
                "autocorrect": autocorrect
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=4, ensure_ascii=False)
                
            logger.info(f"Backup exported successfully to {file_path}")
            return True
    except Exception as e:
        logger.error(f"Failed to export backup: {e}")
        return False

def import_backup(file_path: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
            
        if "snippets" not in backup_data or "groups" not in backup_data:
            logger.error("Invalid backup file: missing snippets or groups schema.")
            return False
            
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM snippets")
            cursor.execute("DELETE FROM groups")
            cursor.execute("DELETE FROM autocorrect")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('snippets', 'groups', 'autocorrect')")
            
            for g in backup_data.get("groups", []):
                cursor.execute("""
                    INSERT INTO groups (id, name, description) 
                    VALUES (?, ?, ?)
                """, (g.get("id"), g.get("name"), g.get("description")))
                
            for s in backup_data.get("snippets", []):
                cursor.execute("""
                    INSERT INTO snippets (
                        id, shortcut, replacement, group_id, tags, description, language,
                        enabled, favorite, usage_counter, created_date, modified_date,
                        hotkey, regex_enabled, app_filter, window_filter, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.get("id"), s.get("shortcut"), s.get("replacement"), s.get("group_id"),
                    s.get("tags", ""), s.get("description", ""), s.get("language", "Plain Text"),
                    s.get("enabled", 1), s.get("favorite", 0), s.get("usage_counter", 0),
                    s.get("created_date"), s.get("modified_date"), s.get("hotkey"),
                    s.get("regex_enabled", 0), s.get("app_filter"), s.get("window_filter"),
                    s.get("notes")
                ))
                
            for a in backup_data.get("autocorrect", []):
                cursor.execute("""
                    INSERT INTO autocorrect (typo, correction) 
                    VALUES (?, ?)
                """, (a.get("typo"), a.get("correction")))
                
            conn.commit()
            logger.info("Backup imported successfully.")
            return True
    except Exception as e:
        logger.error(f"Failed to import backup: {e}")
        return False

# excel export/import
def export_to_excel(snippets: list, file_path: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Snippets"
    ws.append(["Shortcut", "Replacement", "Group", "Tags", "Description", "Language", "Enabled", "Favorite"])
    
    groups = {g.id: g.name for g in get_all_groups()}
    for s in snippets:
        g_name = groups.get(s.group_id, "General")
        ws.append([
            s.shortcut, s.replacement, g_name, ",".join(s.tags),
            s.description, s.language, str(s.enabled), str(s.favorite)
        ])
    wb.save(file_path)

def import_from_excel(file_path: str) -> int:
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    count = 0
    
    groups = {g.name.lower(): g.id for g in get_all_groups()}
    rows = list(ws.iter_rows(values_only=True))
    
    if len(rows) > 1:
        for r in rows[1:]:
            if not r or len(r) < 2 or not r[0] or not r[1]:
                continue
            shortcut, replacement = r[0], r[1]
            group_name = r[2] if len(r) > 2 else "General"
            tags_str = r[3] if len(r) > 3 else ""
            description = r[4] if len(r) > 4 else ""
            language = r[5] if len(r) > 5 else "Plain Text"
            enabled = r[6] if len(r) > 6 else True
            favorite = r[7] if len(r) > 7 else False
            
            g_name = str(group_name or "General")
            if g_name.lower() not in groups:
                g_id = add_group(Group(name=g_name, description="Imported via Excel"))
                groups[g_name.lower()] = g_id
            else:
                g_id = groups[g_name.lower()]
                
            tags = [t.strip() for t in str(tags_str or "").split(",") if t.strip()]
            existing = get_snippet_by_shortcut(shortcut)
            if existing:
                continue
                
            snippet = Snippet(
                shortcut=shortcut,
                replacement=replacement,
                group_id=g_id,
                tags=tags,
                description=str(description or ""),
                language=str(language or "Plain Text"),
                enabled=(str(enabled).lower() == "true" or enabled == 1 or enabled is True),
                favorite=(str(favorite).lower() == "true" or favorite == 1 or favorite is True)
            )
            add_snippet(snippet)
            count += 1
    return count

# yaml export/import
def export_to_yaml(snippets: list, file_path: str):
    groups = {g.id: g.name for g in get_all_groups()}
    data = []
    for s in snippets:
        data.append({
            "shortcut": s.shortcut,
            "replacement": s.replacement,
            "group": groups.get(s.group_id, "General"),
            "tags": s.tags,
            "description": s.description,
            "language": s.language,
            "enabled": s.enabled,
            "favorite": s.favorite
        })
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

def import_from_yaml(file_path: str) -> int:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        return 0
        
    groups = {g.name.lower(): g.id for g in get_all_groups()}
    count = 0
    for item in data:
        shortcut = item.get("shortcut")
        replacement = item.get("replacement")
        if not shortcut or not replacement:
            continue
            
        g_name = item.get("group", "General")
        if g_name.lower() not in groups:
            g_id = add_group(Group(name=g_name, description="Imported via YAML"))
            groups[g_name.lower()] = g_id
        else:
            g_id = groups[g_name.lower()]
            
        existing = get_snippet_by_shortcut(shortcut)
        if existing:
            continue
            
        snippet = Snippet(
            shortcut=shortcut,
            replacement=replacement,
            group_id=g_id,
            tags=item.get("tags", []),
            description=item.get("description", ""),
            language=item.get("language", "Plain Text"),
            enabled=bool(item.get("enabled", True)),
            favorite=bool(item.get("favorite", False))
        )
        add_snippet(snippet)
        count += 1
    return count

# json export/import
def export_to_json(snippets: list, file_path: str):
    groups = {g.id: g.name for g in get_all_groups()}
    data = []
    for s in snippets:
        data.append({
            "shortcut": s.shortcut,
            "replacement": s.replacement,
            "group": groups.get(s.group_id, "General"),
            "tags": s.tags,
            "description": s.description,
            "language": s.language,
            "enabled": s.enabled,
            "favorite": s.favorite
        })
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def import_from_json(file_path: str) -> int:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return 0
        
    groups = {g.name.lower(): g.id for g in get_all_groups()}
    count = 0
    for item in data:
        shortcut = item.get("shortcut")
        replacement = item.get("replacement")
        if not shortcut or not replacement:
            continue
            
        g_name = item.get("group", "General")
        if g_name.lower() not in groups:
            g_id = add_group(Group(name=g_name, description="Imported via JSON"))
            groups[g_name.lower()] = g_id
        else:
            g_id = groups[g_name.lower()]
            
        existing = get_snippet_by_shortcut(shortcut)
        if existing:
            continue
            
        snippet = Snippet(
            shortcut=shortcut,
            replacement=replacement,
            group_id=g_id,
            tags=item.get("tags", []),
            description=item.get("description", ""),
            language=item.get("language", "Plain Text"),
            enabled=bool(item.get("enabled", True)),
            favorite=bool(item.get("favorite", False))
        )
        add_snippet(snippet)
        count += 1
    return count
