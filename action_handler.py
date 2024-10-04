from typing import Tuple

import Live
from ableton.v2.control_surface.component import Component

class ActionHandler(Component):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ActionHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, manager):
        self.manager = manager
        self.logger = self.manager.logger

    def handle_request(self, request_str):
        self.logger.info(f"ActionHandler::handle_request - {request_str}")

        # strip header
        request_id = request_str[6:14]
        message_size = int(request_str[14:22])
        command_str = request_str[22:22 + message_size]

        commands = command_str.split(';')
        parsed_commands = []
        for command in commands:
            parts = command.split(',')
            action = parts[0].lower()
            parameters = parts[1:] if len(parts) > 1 else []
            parsed_commands.append((action, parameters))

        for action, params in parsed_commands:
            method = getattr(self, action, None)
        if callable(method):
            method(request_id, *params)
        else:
            print(f"No such action: {action}")

    def ready(self, request_id):
        self.logger.info(f"library ready, increasing tick frequency")
        self.manager.tickInterval = 1
        self.manager.ipc.write_response_chunks("SPAGHETTI", request_id)

    def path(self, request_id):
        self.manager.ipc.write_response_chunks(
            self.manager.module_path
            , request_id
        )

    def plugins(self, request_id):
        self.manager.ipc.write_response_chunks(
            "|".join(
                [
                    f"{i},{item.name},{item.uri}"
                    for i, item in enumerate(self.manager.plugin_manager.loadable_items())
                ]
            )
            , request_id
        )

    def load_item(self, request_id, *items):
        self.logger.info(f"calling load_item with params: {', '.join(items)}")
        application = Live.Application.get_application()
        browser = application.browser

        for item in items:
            try:
                browser_item = self.manager.plugin_manager.cached_plugin_data[int(item)]
                browser.load_item(browser_item)
            except Exception as e:
                self.manager.logger.error(f"Failed to load item {item}: {e}")

        self.manager.ipc.write_response_chunks(
            "success"
            , request_id
        )
