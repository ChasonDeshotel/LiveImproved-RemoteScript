import Live
from ableton.v2.control_surface.component import Component
from typing import Optional, Tuple, Any
import os
import errno
import select

class IPCUtils(Component):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(IPCUtils, cls).__new__(cls)
        return cls._instance

    def __init__(self, manager):
        self.manager = manager
        self.logger = self.manager.logger
        self.is_writing = False
        self.pipe_fd_write = None
        self.pipe_fd_read = None

        self.is_read_initialized = False

        ##
        ##
        ## fix
        self.is_write_initialized = False

        # ableton script reads requests from lim_request
        # and responds to lim_response
        self.response_pipe_path = os.path.join(self.manager.module_path, 'lim_response')
        self.request_pipe_path = os.path.join(self.manager.module_path, 'lim_request')

    def init_write(self):
        """Try to write the 'READY' message to the response pipe."""
        self.manager.logger.info("IPC::init_write() called")

        if not self.check_or_create_pipe(self.response_pipe_path):
            self.logger.info("IPC::init_write() failed to create or find the response pipe")
            return False

        if not self.open_pipe_for_write(self.response_pipe_path, non_blocking=True):
            self.manager.logger.info("IPC::init_write() failed to open response pipe for writing")

            self.manager.logger.info(f"scheduling the next write pipe check")
            self.manager.schedule_message(1, self.init_write)
            return False

        self.write_response("READY")
        self.manager.logger.info("READY written to response pipe")
        self.is_write_initialized = True
        return True


    def init_read(self):
        """Initialize the read pipe to receive requests."""
        self.manager.logger.info("IPC::init_read() called")

        if not self.check_or_create_pipe(self.request_pipe_path):
            self.logger.info("IPC::init_read() failed to create or find the request pipe")
            return False

        if not self.open_pipe_for_read(self.request_pipe_path, non_blocking=True):
            self.manager.logger.info("IPC::init_read() failed to open request pipe for reading")
            self.manager.logger.info("scheduling the next read pipe check")
            self.manager.schedule_message(1, self.init_read)
            return False

        self.manager.logger.info("Request pipe successfully opened for reading")
        self.is_read_initialized = True
        return True

    def check_or_create_pipe(self, pipe_name: str) -> bool:
        """Check if the pipe exists, and if not, create it."""
        if not os.path.exists(pipe_name):
            try:
                os.mkfifo(pipe_name)
                self.manager.logger.info(f"Pipe created: {pipe_name}")
                return True
            except OSError as e:
                self.manager.logger.info(f"Failed to create pipe: {pipe_name} - {e}")
                return False
        else:
            self.logger.info(f"Pipe already exists: {pipe_name}")
        return True

    def open_pipe_for_write(self, pipe_name: str, non_blocking: bool) -> bool:
        """Open the pipe for writing."""
        flags = os.O_WRONLY
        if non_blocking:
            flags |= os.O_NONBLOCK

        try:
            self.pipe_fd_write = os.open(pipe_name, flags)
            self.manager.logger.info(f"Pipe opened for writing: {pipe_name}")
            return True
        except OSError as e:
            self.manager.logger.info(f"Failed to open pipe for writing: {pipe_name} - {e}")
            
        return False

    def open_pipe_for_read(self, pipe_name: str, non_blocking: bool) -> bool:
        """Open the pipe for reading."""
        flags = os.O_RDONLY
        if non_blocking:
            flags |= os.O_NONBLOCK

        try:
            self.pipe_fd_read = os.open(pipe_name, flags)
            self.manager.logger.info(f"Pipe opened for reading: {pipe_name}")
            return True
        except OSError as e:
            self.manager.logger.info(f"Failed to open pipe for reading: {pipe_name} - {e}")
            return False


    def read_request(self):
        """Helper method to read a request from the request pipe."""
        self.manager.logger.info("read request")
        data = self.read_from_pipe(self.pipe_fd_read)
        if data:
            return data.decode('utf-8')
        return None

    def read_from_pipe(self, fh):
        rlist, _, _ = select.select([fh], [], [], 0)
        if rlist:
            data = os.read(fh, 1024)
            if data:
                self.manager.logger.info(f"Read data from pipe: {data}")
                return data
            else:
                self.manager.logger.info("No data available in pipe")
                return

    def write_response(self, response: str):
        """Helper method to write a response to the response pipe."""
        return self.write_to_pipe(response)

    def write_to_pipe(self, response):
        self.manager.logger.info("calling write_to_pipe")

        if not self.pipe_fd_write:
            self.manager.logger.info("no write pipe exists")
            return False

        if self.is_writing == False:
            self.manager.logger.info("calling write pipe")

            self.is_writing = True
            response_length = len(response)
            header = f"{response_length:04d}"  # Create a 4-character wide header
            try:
                self.manager.logger.info("calling os write")
                os.write(self.pipe_fd_write, (header + response).encode())
                self.manager.logger.info("after os write")
            except Exception as e:
                self.manager.logger.info(f"write failed: {e}")
                self.is_writing = False
                return False
            
            self.is_writing = False
            self.manager.logger.info("wrote to pipe")
            return True

