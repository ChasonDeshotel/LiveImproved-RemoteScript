import Live
from ableton.v2.control_surface.component import Component
from typing import Optional, Tuple, Any
import logging
import os

class PluginManager(Component):
    def __init__(self, manager):
        super().__init__(manager)

        self.manager = manager

        self.cached_plugin_data = []

    def loadable_items(self):
        return self.cached_plugin_data;

    def cache_plugins(self):
        def find_loadable_items(item, loadable_items=None, depth=0, max_depth=5):
            if loadable_items is None:
                loadable_items = []

            if depth > max_depth:
                self.manager.logger.info(f"Max recursion depth reached at item: {item.name}")
                return loadable_items

            if item.is_loadable:
                f.write(f"{item.name},{item.uri},{item.is_loadable}\n")
                loadable_items.append(item)
            else:
                if item.children:
                    for child in item.children:
                        find_loadable_items(child, loadable_items, depth + 1, max_depth)
            # newline so you know it's complete
            #f.write(f"\n")
            return loadable_items

        self.manager.logger.info("starting cache");

        loadable_items = []
        self.cached_plugin_data = []

        application = Live.Application.get_application()
        browser = application.browser

        f = open(os.path.join(self.manager.module_path, "loadable_items.txt"), "w")

        try:
            #AU, VST, VST3
            for i in range(2):
                for item in browser.plugins.children[i].children:
                    find_loadable_items(item, loadable_items)

            self.cached_plugin_data = loadable_items
            self.manager.logger.info(f"Cached {len(loadable_items)} loadable items successfully.")

            for item in loadable_items:
                self.manager.logger.info(f"Name: {item.name}, URI: {item.uri}, Loadable: {item.is_loadable}")

        except Exception as e:
            self.manager.logger.error(f"failed cache: {e}");
            return "error during caching",

        return self.cached_plugin_data,
