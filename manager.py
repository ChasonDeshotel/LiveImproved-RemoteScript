from typing import Tuple

import traceback
import logging
import sys
import os

import Live
from ableton.v2.control_surface import ControlSurface

from .ipc_utils import IPCUtils
from .event_processor import EventProcessor
from .plugin_manager import PluginManager
from .action_handler import ActionHandler

logger = logging.getLogger("Lim")

class Manager(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)

        self.max_ipc_retries   = 500
        self.attempt           = 0
        self.fast_ticks        = 1
        self.slow_ticks        = 50
        self.really_slow_ticks = 500

        self.logger = logger
        self.tickInterval = 5;
        self.module_path = os.path.dirname(os.path.realpath(__file__))

        self.log_level = "info"
        self.start_logging()
        logger.info("Lim: started")

        with self.component_guard():
            self.ipc = IPCUtils(self)
            self.event_processor = EventProcessor(self)
            self.plugin_manager = PluginManager(self)
            self.action_handler = ActionHandler(self)

        self.schedule_message(5, self.init)

        self.schedule_message(1, self.main_loop)

        self.schedule_message(1, self.plugin_manager.cache_plugins)

    def main_loop(self):
        #self.logger.debug("main loop tick")

        data = self.ipc.read_request()

        if data:
            self.logger.info(f"data: {data}")
            self.action_handler.handle_request(data)

        self.schedule_message(self.tickInterval, self.main_loop)

    def wait_for_ready(self):
        data = self.ipc.read_request()

        if data and data == 'READY':
            self.logger.info("READY received, starting main loop...");
            return 1;

        self.schedule_message(self.tickInterval, self.wait_for_ready)


    def init(self):
        """Initialize the read and write pipes."""
        self.logger.info(f"init ipc pipes. attempt {self.attempt}")

        self.attempt += 1

        if not self.ipc.is_write_initialized:
            # loops until able to send READY
            self.schedule_message(1, self.ipc.init_write)
        
        if not self.ipc.is_read_initialized:
            # loops until request pipe is readable
            self.schedule_message(1, self.ipc.init_read)


        # TODO logic to read/write READY before progressing
        if self.ipc.is_read_initialized and self.ipc.is_write_initialized:
            self.logger.info("Both pipes initialized, waiting for READY...")

            self.ipc.write_response("READY")
            self.logger.info("READY written to response pipe...")

            # TODO wait for response

#            self.schedule_message(1, self.wait_for_ready)
            return True
        else:
            self.logger.info("Pipes not yet initialized")

            if self.attempt < 51:
                self.schedule_message(self.fast_ticks, self.init)
            elif self.attempt < 500:
                self.schedule_message(self.slow_ticks, self.init)
            else:
                self.schedule_message(self.really_slow_ticks, self.init)

            return False

    def start_logging(self):
        """
        Start logging to a local logfile (logs/log.txt),
        """
        module_path = os.path.dirname(os.path.realpath(__file__))
        log_dir = os.path.join(module_path, "logs")
        if not os.path.exists(log_dir):
            os.mkdir(log_dir, 0o755)
        log_path = os.path.join(log_dir, "log.txt")
        self.log_file_handler = logging.FileHandler(log_path)
        self.log_file_handler.setLevel(self.log_level.upper())
        formatter = logging.Formatter('(%(asctime)s) [%(levelname)s] %(message)s')
        self.log_file_handler.setFormatter(formatter)
        logger.addHandler(self.log_file_handler)

    def stop_logging(self):
        logger.removeHandler(self.log_file_handler)

#    def reload_imports(self):
#        try:
#            importlib.reload(.action_handler)
#            importlib.reload(.ipc_utils)
#        except Exception as e:
#            exc = traceback.format_exc()
#            logging.warning(exc)

