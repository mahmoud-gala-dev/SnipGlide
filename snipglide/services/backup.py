import csv
import json
import yaml
import openpyxl
from typing import List
from snipglide.models.snippet import Snippet
from snipglide.database.snippet_repo import add_snippet, get_snippet_by_shortcut, update_snippet
from snipglide.database.group_repo import get_all_groups, add_group, get_group_by_name
from snipglide.models.group import Group
from snipglide.utils.logger import logger

def export_to_json(snippets: List[Snippet], file_path: str):
    data = []
    groups = {g.id: g.name for g in get_all_groups()}
    for snippet in snippets:
        item = snippet.__dict__.copy()
        item["group_name"] = groups.get(snippet.group_id, "General")
        data.append(item)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def import_from_json(file_path: str) -> int:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    imported = 0
    groups = {g.name: g.id for g in get_all_groups()}
    for item in data:
        group_name = item.get("group_name", "General")
        if group_name not in groups:
            g_id = add_group(Group(name=group_name))
            groups[group_name] = g_id
        g_id = groups[group_name]
        
        snippet = Snippet(
            shortcut=item["shortcut"],
            replacement=item["replacement"],
            group_id=g_id,
            tags=item.get("tags", []),
            description=item.get("description", ""),
            language=item.get("language", "Plain Text"),
            enabled=bool(item.get("enabled", True)),
            favorite=bool(item.get("favorite", False)),
            hotkey=item.get("hotkey", ""),
            regex_enabled=bool(item.get("regex_enabled", False)),
            app_filter=item.get("app_filter", ""),
            window_filter=item.get("window_filter", ""),
            notes=item.get("notes", "")
        )
        
        existing = get_snippet_by_shortcut(snippet.shortcut)
        if existing:
            snippet.id = existing.id
            update_snippet(snippet)
        else:
            add_snippet(snippet)
        imported += 1
    return imported

def export_to_yaml(snippets: List[Snippet], file_path: str):
    data = []
    groups = {g.id: g.name for g in get_all_groups()}
    for snippet in snippets:
        item = snippet.__dict__.copy()
        item["group_name"] = groups.get(snippet.group_id, "General")
        data.append(item)
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)

def import_from_yaml(file_path: str) -> int:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return 0
    imported = 0
    groups = {g.name: g.id for g in get_all_groups()}
    for item in data:
        group_name = item.get("group_name", "General")
        if group_name not in groups:
            g_id = add_group(Group(name=group_name))
            groups[group_name] = g_id
        g_id = groups[group_name]
        
        snippet = Snippet(
            shortcut=item["shortcut"],
            replacement=item["replacement"],
            group_id=g_id,
            tags=item.get("tags", []),
            description=item.get("description", ""),
            language=item.get("language", "Plain Text"),
            enabled=bool(item.get("enabled", True)),
            favorite=bool(item.get("favorite", False)),
            hotkey=item.get("hotkey", ""),
            regex_enabled=bool(item.get("regex_enabled", False)),
            app_filter=item.get("app_filter", ""),
            window_filter=item.get("window_filter", ""),
            notes=item.get("notes", "")
        )
        existing = get_snippet_by_shortcut(snippet.shortcut)
        if existing:
            snippet.id = existing.id
            update_snippet(snippet)
        else:
            add_snippet(snippet)
        imported += 1
    return imported

def export_to_csv(snippets: List[Snippet], file_path: str):
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Shortcut", "Replacement", "Group", "Tags", "Description", "Language", "Enabled", "Favorite"])
        groups = {g.id: g.name for g in get_all_groups()}
        for s in snippets:
            g_name = groups.get(s.group_id, "General")
            writer.writerow([s.shortcut, s.replacement, g_name, ",".join(s.tags), s.description, s.language, int(s.enabled), int(s.favorite)])

def import_from_csv(file_path: str) -> int:
    imported = 0
    groups = {g.name: g.id for g in get_all_groups()}
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            shortcut = row[0].strip()
            replacement = row[1]
            if not shortcut:
                continue
                
            group_name = row[2].strip() if len(row) > 2 else "General"
            if not group_name:
                group_name = "General"
            if group_name not in groups:
                g_id = add_group(Group(name=group_name))
                groups[group_name] = g_id
            g_id = groups[group_name]
            
            tags = [t.strip() for t in row[3].split(",") if t.strip()] if len(row) > 3 else []
            description = row[4].strip() if len(row) > 4 else ""
            language = row[5].strip() if len(row) > 5 else "Plain Text"
            enabled = int(row[6]) if len(row) > 6 and row[6].isdigit() else 1
            favorite = int(row[7]) if len(row) > 7 and row[7].isdigit() else 0
            
            snippet = Snippet(
                shortcut=shortcut,
                replacement=replacement,
                group_id=g_id,
                tags=tags,
                description=description,
                language=language,
                enabled=bool(enabled),
                favorite=bool(favorite)
            )
            existing = get_snippet_by_shortcut(snippet.shortcut)
            if existing:
                snippet.id = existing.id
                update_snippet(snippet)
            else:
                add_snippet(snippet)
            imported += 1
    return imported

def export_to_excel(snippets: List[Snippet], file_path: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Snippets"
    ws.append(["Shortcut", "Replacement", "Group", "Tags", "Description", "Language", "Enabled", "Favorite"])
    groups = {g.id: g.name for g in get_all_groups()}
    for s in snippets:
        g_name = groups.get(s.group_id, "General")
        ws.append([s.shortcut, s.replacement, g_name, ",".join(s.tags), s.description, s.language, "TRUE" if s.enabled else "FALSE", "TRUE" if s.favorite else "FALSE"])
    wb.save(file_path)

def import_from_excel(file_path: str) -> int:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active
    imported = 0
    groups = {g.name: g.id for g in get_all_groups()}
    
    headers = [str(cell.value).strip().lower() if cell.value is not None else "" for cell in sheet[1]]
    shortcut_idx = 0
    replacement_idx = 1
    group_idx = 2
    tags_idx = 3
    description_idx = 4
    language_idx = 5
    enabled_idx = 6
    favorite_idx = 7
    
    has_headers = False
    for i, h in enumerate(headers):
        if any(x in h for x in ["shortcut", "trigger"]):
            shortcut_idx = i
            has_headers = True
        elif any(x in h for x in ["replacement", "text"]):
            replacement_idx = i
            has_headers = True
        elif "group" in h:
            group_idx = i
            has_headers = True
        elif "tag" in h:
            tags_idx = i
            has_headers = True
        elif "description" in h:
            description_idx = i
            has_headers = True
        elif "language" in h or "syntax" in h:
            language_idx = i
            has_headers = True
        elif "enabled" in h:
            enabled_idx = i
            has_headers = True
        elif "favorite" in h:
            favorite_idx = i
            has_headers = True
            
    start_row = 2 if has_headers else 1
    for row_num in range(start_row, sheet.max_row + 1):
        shortcut_val = sheet.cell(row=row_num, column=shortcut_idx + 1).value
        if shortcut_val is None:
            continue
        shortcut = str(shortcut_val).strip()
        if not shortcut:
            continue
            
        replacement_val = sheet.cell(row=row_num, column=replacement_idx + 1).value
        replacement = str(replacement_val) if replacement_val is not None else ""
        
        group_val = sheet.cell(row=row_num, column=group_idx + 1).value if sheet.max_column > group_idx else "General"
        group_name = str(group_val).strip() if group_val is not None else "General"
        if not group_name:
            group_name = "General"
        if group_name not in groups:
            g_id = add_group(Group(name=group_name))
            groups[group_name] = g_id
        g_id = groups[group_name]
        
        tags_val = sheet.cell(row=row_num, column=tags_idx + 1).value if sheet.max_column > tags_idx else ""
        tags = [t.strip() for t in str(tags_val).split(",") if t.strip()] if tags_val else []
        
        desc_val = sheet.cell(row=row_num, column=description_idx + 1).value if sheet.max_column > description_idx else ""
        description = str(desc_val).strip() if desc_val is not None else ""
        
        lang_val = sheet.cell(row=row_num, column=language_idx + 1).value if sheet.max_column > language_idx else "Plain Text"
        language = str(lang_val).strip() if lang_val is not None else "Plain Text"
        
        enabled_val = sheet.cell(row=row_num, column=enabled_idx + 1).value if sheet.max_column > enabled_idx else "TRUE"
        enabled = str(enabled_val).strip().upper() not in ["FALSE", "0", "OFF"]
        
        fav_val = sheet.cell(row=row_num, column=favorite_idx + 1).value if sheet.max_column > favorite_idx else "FALSE"
        favorite = str(fav_val).strip().upper() in ["TRUE", "1", "YES"]
        
        snippet = Snippet(
            shortcut=shortcut,
            replacement=replacement,
            group_id=g_id,
            tags=tags,
            description=description,
            language=language,
            enabled=enabled,
            favorite=favorite
        )
        existing = get_snippet_by_shortcut(snippet.shortcut)
        if existing:
            snippet.id = existing.id
            update_snippet(snippet)
        else:
            add_snippet(snippet)
        imported += 1
    return imported

def import_from_espanso(file_path: str) -> int:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "matches" not in data:
        return 0
    imported = 0
    g = get_group_by_name("General")
    g_id = g.id if g else 1
    
    for item in data["matches"]:
        trigger = item.get("trigger")
        word = item.get("word")
        replace = item.get("replace")
        
        shortcut = trigger or word
        replacement = replace
        if not shortcut or not replacement:
            continue
            
        snippet = Snippet(
            shortcut=shortcut,
            replacement=replacement,
            group_id=g_id,
            description="Imported from Espanso"
        )
        existing = get_snippet_by_shortcut(snippet.shortcut)
        if existing:
            snippet.id = existing.id
            update_snippet(snippet)
        else:
            add_snippet(snippet)
        imported += 1
    return imported
