import Live
from ableton.v2.control_surface import ControlSurface

from typing import Tuple

import traceback
import logging
import sys
import os

from .ipc_utils import IPCUtils
from .event_processor import EventProcessor
from .plugin_manager import PluginManager

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

        self.schedule_message(1, self.tick)

        self.plugin_manager.cache_plugins()

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
#        self.cache_plugins()
        
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



    def tick(self):
        """
        Called once per 100ms "tick".
        Live's embedded Python implementation does not appear to support threading,
        and beachballs when a thread is started. Instead, this approach allows long-running
        processes.
        """
        logger.debug("Tick...")
        self.event_processor.tick()

        #res = self.ipc.read(self.ipc.pipe_fd_read)
        #if len(res):
        #    logger.info(res)

        #self.schedule_message(1, self.tick)

    def reload_imports(self):
        try:
            importlib.reload(liveenhancedenhancer)
        except:
            pass

