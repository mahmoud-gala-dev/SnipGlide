import os
import threading
import time
from datetime import datetime
from snipglide.core.config import BACKUP_DIR
from snipglide.database.snippet_repo import get_all_snippets
from snipglide.services.backup import export_to_json
from snipglide.utils.logger import logger

def run_auto_backup():
    """Runs a daily auto-backup of all snippets, keeping the latest 7 backup files."""
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        backup_file = BACKUP_DIR / f"auto_backup_{today_str}.json"
        
        if not backup_file.exists():
            snippets = get_all_snippets()
            if snippets:
                export_to_json(snippets, str(backup_file))
                logger.info(f"Daily auto-backup created: {backup_file.name}")

        # Prune old auto-backups keeping only latest 7
        auto_backups = sorted(BACKUP_DIR.glob("auto_backup_*.json"))
        if len(auto_backups) > 7:
            for old_file in auto_backups[:-7]:
                try:
                    old_file.unlink()
                    logger.info(f"Pruned old auto-backup: {old_file.name}")
                except Exception as e:
                    logger.error(f"Failed to prune old backup {old_file.name}: {e}")
    except Exception as e:
        logger.error(f"Auto-backup failed: {e}")

def start_auto_backup_service():
    """Launches auto-backup in a background thread."""
    def _worker():
        time.sleep(5)  # Delay start to avoid app launch contention
        run_auto_backup()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
