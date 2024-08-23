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

        self.logger = logger
        self.module_path = os.path.dirname(os.path.realpath(__file__))

        self.log_level = "info"
        self.start_logging()
        logger.info("Lim: started")

        with self.component_guard():
            self.ipc = IPCUtils(self)
            self.event_processor = EventProcessor(self)
            self.plugin_manager = PluginManager(self)
            self.action_handler = ActionHandler(self)

        self.init()
        self.plugin_manager.cache_plugins()

    def main_loop(self):
        #self.logger.debug("main loop tick")

        data = self.ipc.read_request()

        if data:
            self.logger.info(f"data: {data}")
            self.action_handler.handle_request(data)

        ##
        ## TODO: receive a READY signal from the injected library
        ## then shorten the tick
        ##
        self.schedule_message(5, self.main_loop)

    def init(self):
        """Initialize the read and write pipes."""
        if not self.ipc.is_write_initialized:
            # loops until able to send READY
            self.schedule_message(1, self.ipc.init_write)
        
        if not self.ipc.is_read_initialized:
            # loops until request pipe is readable
            self.schedule_message(1, self.ipc.init_read)

        if self.ipc.is_read_initialized and self.ipc.is_write_initialized:
            self.logger.info("Both pipes initialized, starting the main loop")
            self.schedule_message(1, self.main_loop)
        else:
            self.logger.info("Pipes not yet initialized, rechecking...")
            self.schedule_message(1, self.init)

#        app = Live.Application.get_application()
#        logger.info(f"pointer: {hex(id(app))}")
#
#        live_ptr = app._live_ptr
#        logger.info(f"_live_ptr: {hex(live_ptr)}")
#
#        browser = app.browser
#        logger.info(f"pointer: {hex(id(browser))}")
#
#        browser_ptr = browser._live_ptr
#        logger.info(f"browser._live_ptr: {hex(browser_ptr)}")
#
#        #self.read(self.pipe_fd_read)
#        self.write(self.pipe_fd_write)
#
        # or export PYTHONPATH="/path/to/your/library:$PYTHONPATH"
        # on windows: set PYTHONPATH=C:\path\to\your\library;%PYTHONPATH%
#        import shared_memory

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

