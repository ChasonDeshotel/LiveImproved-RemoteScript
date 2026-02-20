from typing import Tuple

import traceback
import logging
import sys
import os
import threading
import time

if not hasattr(sys.stderr, 'flush'):
    sys.stderr.flush = lambda: None

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

sys.path.insert(0, "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Python/abl.webconnector/abl")
sys.path.insert(0, "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Python/abl.webconnector/abl/installer")
sys.path.insert(0, "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Python/abl.webconnector/abl/webconnector")

import Live
from ableton.v2.control_surface import ControlSurface

from .ipc_utils import IPCUtils
from .ipc_utils import TCPTransport
from .event_processor import EventProcessor
from .plugin_manager import PluginManager
from .action_handler import ActionHandler

logger = logging.getLogger("Lim")

class PipeListener(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
    
    def run(self):
        while True:
            try:
                logger.info("thread")
            except Exception as e:
                pass

class Manager(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)

        self.liveApp = Live.Application.get_application()
        self.max_ipc_retries   = 500
        self.attempt           = 0
        self.fast_ticks        = 1
        self.slow_ticks        = 50
        self.really_slow_ticks = 500
        self.fast_retry        = 0.5
        self.slow_retry        = 10
        self.really_slow_retry = 120

        self.logger = logger
        self.tickInterval = 5;
        self.module_path = os.path.dirname(os.path.realpath(__file__))

        self.log_level = "info"
        self.start_logging()
        logger.info("Lim: started")
        logger.info(sys.version)           # full version string
        logger.info(sys.version_info)      # named tuple, easy to compare

        logger.info(sys.path)
        logger.info([x for x in sys.path if x]) 

        logger.info(f"sys.path: {sys.path}")
        logger.info(f"EXTENSION_SUFFIXES: {sys.path}")

        try:
            import importlib.machinery
            logger.info(f"suffixes: {importlib.machinery.EXTENSION_SUFFIXES}")
            import socket
        except Exception as e:
            logger.error(f"import failed: {type(e).__name__}: {e}")

        with self.component_guard():
            self.event_processor = EventProcessor(self)
            self.plugin_manager = PluginManager(self)
            self.action_handler = ActionHandler(self)
            self.ipc = TCPTransport(self, self.action_handler)

        try:
            from AbletonIPC import create_ipc_channel
            logger.info("AbletonIPC available!")
        except ImportError as e:
            logger.info(f"AbletonIPC not available: {e}")


        # kick off init in a thread so it doesn't block
        threading.Thread(target=self.init, daemon=True).start()

        #self.schedule_message(1, self.main_loop)


    #def main_loop(self):
    #    data = self.ipc.read_request()

    #    if data:
    #        self.logger.info(f"data: {data}")
    #        self.action_handler.handle_request(data)

    #    self.schedule_message(self.tickInterval, self.main_loop)

    #def wait_for_ready(self):
    #    data = self.ipc.read_request()

    #    if data and data == 'READY':
    #        self.logger.info("READY received, starting main loop...");
    #        return 1;

    #    self.schedule_message(self.tickInterval, self.wait_for_ready)


    def init(self):
        """Initialize the read and write pipes."""
        self.logger.info("IPC init started")
        self.attempt = 0;

        while not (self.ipc.is_read_initialized and self.ipc.is_write_initialized):
            self.logger.info(f"init ipc. attempt {self.attempt}")
            self.attempt += 1
            if self.ipc.connect():
                ## cache plugins after IPC is connected
                ## plugin data isn't available until late in Live startup
                ## IPC happens pretty instantaneously once MIDI Scripts are booted
                ## which is almost the exact moment plugin/browser data becomes available
                ## so we hack in the plugin cache refresh here

                ## also, the first request LiveImproved makes is for plugins...
                ## so waiting until after the plugin cache is plenished to send READY
                ## simplifies the startup synchronization
                self.schedule_message(1, self.plugin_manager.cache_plugins)

                self.ipc.start()
                self.ipc.send("READY", 0)
                break
        #    
        #    if not self.ipc.is_write_initialized:
        #        self.logger.info("initializing write pipe")
        #        self.ipc.init_write()

        #    if not self.ipc.is_read_initialized:
        #        self.logger.info("initializing read pipe")
        #        self.ipc.init_read()

        #    ## TODO logic to read/write READY before progressing
        #    if self.ipc.is_read_initialized and self.ipc.is_write_initialized:
        #        break

        #    self.logger.info("Pipes not yet initialized")

            if self.attempt < 51:
                time.sleep(self.fast_retry)
            elif self.attempt < 500:
                time.sleep(self.slow_retry)
            else:
                time.sleep(self.really_slow_retry)

        #self.logger.info("Both pipes initialized, waiting for READY...")

        #self.ipc.write_response("READY")
        #self.logger.info("READY written to response pipe...")
        #self.logger.info("starting IPC thread")
        #self.ipc.start()

        # TODO wait for response
#            self.schedule_message(1, self.wait_for_ready)


        return True

    def disconnect(self):
        self.logger.info("shutting down IPC")
        self.ipc.stop()

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

    def execute_on_main_thread(self, fn):
        fn();

#    def reload_imports(self):
#        try:
#            importlib.reload(.action_handler)
#            importlib.reload(.ipc_utils)
#        except Exception as e:
#            exc = traceback.format_exc()
#            logging.warning(exc)
