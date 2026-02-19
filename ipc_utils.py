import Live
from ableton.v2.control_surface.component import Component
from typing import Optional, Tuple, Any

import os
import errno
import select
import platform
import time
import threading
import socket

class TCPTransport(Component):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TCPTransport, cls).__new__(cls)
        return cls._instance

    def __init__(self, manager, action_handler, host='127.0.0.1', port=47474):
        self.action_handler = action_handler
        self.host = host
        self.port = port
        self.sock = None

        self.manager = manager
        self.logger = manager.logger
        self._stop_event = threading.Event()
        self._read_thread = None
        self._on_message = None  # callback
        self.is_read_initialized = False
        self.is_write_initialized = False

        self.request_id = 0
        self.current_request_id = 0
        self.message_size = 0

        if platform.system() == "Windows":
            self.response_pipe_path = r"\\.\pipe\lim_response"
            self.request_pipe_path = r"\\.\pipe\lim_request"

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)  # don't wait forever per attempt
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # back to blocking after connect
            self.is_read_initialized = True
            self.is_write_initialized = True
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            self.sock = None
            return False

    def send(self, message: str, request_id):
        request_id = int(request_id)
        try:
            message_length = len(message)
            start_marker = f"START_{request_id:08d}{message_length:08d}"
            full_message = f"{start_marker}{message}END_OF_MESSAGE"

            self.sock.sendall(full_message.encode())

            self.logger.info(f"IPC response written: {full_message[:64]}...")
            return True
        except OSError as e:
            self.logger.error(f"Write failed: {e}")
            return False

    def start(self):
        if not self.is_read_initialized:
            self.logger.error("Cannot start IPC thread: read pipe not initialized")
            return
        self._stop_event.clear()
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        self.logger.info("IPC read thread started")

    def stop(self):
        if self.sock:
            self.send("SHUTDOWN", 99999999)

        self._stop_event.set()

        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=2.0)
        
        self.is_read_initialized = False
        self.logger.info("IPC disconnected")

    def _read_loop(self):
        if not self.sock:
            return

        while not self._stop_event.is_set():
            try:
                data = self.sock.recv(2048)
                if data:
                    message = data.decode('utf-8').strip()
                    self.logger.info(f"IPC received: {message}")
                    self._dispatch(message)
                else:
                    # server disconnected
                    self.logger.warn("Server disconnected")
                    self.sock = None
                    break
            except OSError:
                time.sleep(0.01)

    def _dispatch(self, message):
        self.logger.info(f"dispatching: {message}")
        if not message.startswith("START_"):
            self.logger.error(f"Invalid message format: {message}")
            return
        try:
            request_id = message[6:14]
            message_size = int(message[14:22])
            command = message[22:22 + message_size]
            self.logger.info(f"command: {command}")
            self.current_request_id = request_id

            self.action_handler.handle_request(message)

        except (ValueError, IndexError) as e:
            self.logger.error(f"Failed to parse message: {e}")
    
    def recv(self) -> str:
        return self.sock.recv(2048).decode()

class IPCUtils(Component):

    def set_message_callback(self, callback):
        self._on_message = callback

    def init_read(self):
        self.logger.info("IPC::init_read() called")

    def init_write(self):
        self.logger.info("IPC::init_write() called")


    def stop(self):
        self._stop_event.set()
        if self._read_thread:
            self._read_thread.join(timeout=2.0)
        self.logger.info("IPC read thread stopped")



