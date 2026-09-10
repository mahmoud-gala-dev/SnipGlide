"""GUI Smoke Test for SnipGlide Python Pro Developer Suite."""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from snipglide.database.connection import initialize_database
from snipglide.ui_qt.main_window import MainWindowQt
from snipglide.ui_qt.dev_tools.toolbox_page import DevToolboxPageQt

def smoke_test():
    initialize_database()
    app = QApplication.instance() or QApplication(sys.argv)

    print("[1/4] Instantiating MainWindowQt...")
    main_win = MainWindowQt()
    assert main_win is not None
    print("      ✓ MainWindowQt initialized successfully.")

    print("[2/4] Testing Developer Toolbox Tabs...")
    toolbox = main_win.dev_toolbox_page
    num_tabs = toolbox.tabs.count()
    print(f"      ✓ Developer Toolbox has {num_tabs} sub-tool tabs:")
    for i in range(num_tabs):
        tab_name = toolbox.tabs.tabText(i)
        toolbox.tabs.setCurrentIndex(i)
        widget = toolbox.tabs.currentWidget()
        assert widget is not None
        print(f"        - Tab {i+1}: '{tab_name}' -> {widget.__class__.__name__}")
    assert num_tabs == 14, f"Expected 14 tabs, found {num_tabs}"

    print("[3/4] Testing Command Palette routing...")
    dev_actions = [
        "dev_json", "dev_base64", "dev_url", "dev_jwt", "dev_uuid",
        "dev_timestamp", "dev_hash", "dev_text", "dev_regex",
        "dev_api", "dev_git", "dev_ai_coding", "dev_projects", "dev_commands"
    ]
    for act in dev_actions:
        main_win._handle_command_palette_action("action", act)
        print(f"      ✓ Routed action '{act}' successfully.")


    print("[4/4] Testing Search Page...")
    main_win.sidebar.select_page("Search")
    search_page = main_win.search_page
    search_page.search_edit.setText("test")
    search_page._execute_search()
    print(f"      ✓ Search executed with {search_page.results_list.count()} results.")

    print("=" * 60)
    print("ALL SMOKE TESTS PASSED CLEANLY WITH ZERO CRASHES!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(smoke_test())
