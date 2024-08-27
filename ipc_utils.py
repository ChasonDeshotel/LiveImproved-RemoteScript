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

    def write_response(self, message: str):
        """Helper method to write a response to the response pipe."""

        #start_marker = f"MESSAGE_{request_id}_START"
        message_length = len(message)
        start_marker = f"START_11111111{message_length:08d}"
        end_marker = "END_OF_MESSAGE"
        full_message = f"{start_marker}{message}{end_marker}"
        return self.write_to_pipe(full_message)

    def write_to_pipe(self, message):
        self.manager.logger.info("calling write_to_pipe")

        if not self.pipe_fd_write:
            self.manager.logger.info("no write pipe exists")
            return False

        if self.is_writing == False:
            self.manager.logger.info("calling write pipe")

            self.is_writing = True
            try:
                self.manager.logger.info("calling os write")
                os.write(self.pipe_fd_write, message.encode())
                self.manager.logger.info("after os write")
            except Exception as e:
                self.manager.logger.info(f"write failed: {e}")
                self.is_writing = False
                return False

            self.is_writing = False
            self.manager.logger.info("wrote to pipe")
            return True

    def write_response_chunks(self, message):
        """Helper method to write a response to the response pipe."""
        message_length = len(message)
        start_marker = f"START_11111111{message_length:08d}"
        end_marker = "END_OF_MESSAGE"
        full_message = f"{start_marker}{message}{end_marker}"
        return self.write_to_pipe_chunks(full_message)

    def write_to_pipe_chunks(self, message):
        self.manager.logger.info("calling write_to_pipe")

        if not self.pipe_fd_write:
            self.manager.logger.info("no write pipe exists")
            return False

        if not self.is_writing:
            self.manager.logger.info("starting write process")

            self.is_writing = True
            self.manager.logger.info(f"writing message: {message}")
            self.message_bytes = message.encode()
            self.total_written = 0
            self.chunk_size = 8192

            self.manager.logger.info(f"Scheduling first chunk write")
            self.manager.schedule_message(1, self.write_next_chunk)
            return True
        else:
            self.manager.logger.info("Already writing to pipe, skipping...")
            return False

    def write_next_chunk(self):
        """Write the next chunk of the message to the pipe."""
        remaining_bytes = len(self.message_bytes) - self.total_written
        if remaining_bytes > 0:
            chunk = self.message_bytes[self.total_written:self.total_written + self.chunk_size]

            try:
                written = os.write(self.pipe_fd_write, chunk)
                self.total_written += written
                self.manager.logger.info(f"Chunk written: {written} bytes, Total: {self.total_written}/{len(self.message_bytes)}")

                if self.total_written < len(self.message_bytes):
                    # Schedule the next chunk to be written
                    self.manager.schedule_message(1, self.write_next_chunk)
                else:
                    self.manager.logger.info("All chunks written successfully")
                    self.is_writing = False

            except Exception as e:
                self.manager.logger.info(f"Write failed: {e}")
                self.is_writing = False

        else:
            self.manager.logger.info("No remaining bytes to write")
            self.is_writing = False

    def clear_pipe(pipe_path):
        """Clear any existing data from the pipe."""
        try:
            # Open the pipe in non-blocking mode
            with os.open(pipe_path, os.O_RDONLY | os.O_NONBLOCK) as pipe_fd:
                while True:
                    try:
                        # Try to read a chunk of data
                        data = os.read(pipe_fd, 4096)  # Adjust the buffer size if needed
                        if not data:
                            break  # Break the loop if no more data is available
                    except OSError as e:
                        if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                            break  # No more data available to read
                        else:
                            raise  # Re-raise any other exceptions
        except FileNotFoundError:
            print(f"Pipe {pipe_path} not found.")
        except Exception as e:
            print(f"Error while clearing the pipe: {e}")
