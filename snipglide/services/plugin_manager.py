import os
import importlib.util
from typing import Dict
from snipglide.core.config import PLUGINS_DIR
from snipglide.utils.logger import logger

class PluginManager:
    def __init__(self):
        self.plugins: Dict = {}
        
    def load_plugins(self):
        if not PLUGINS_DIR.exists():
            return
            
        for file in os.listdir(PLUGINS_DIR):
            if file.endswith(".py") and not file.startswith("__"):
                plugin_path = PLUGINS_DIR / file
                plugin_name = file[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, "register_plugin"):
                            self.plugins[plugin_name] = module.register_plugin()
                            logger.info(f"Loaded plugin: {plugin_name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_name}: {e}")

plugin_manager = PluginManager()
