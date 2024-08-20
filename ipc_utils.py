import Live
from ableton.v2.control_surface.component import Component
from typing import Optional, Tuple, Any
import logging
import os
import errno

class IPCUtils(Component):
    def __init__(self, manager):
        super().__init__(manager)

        self.manager = manager

        self.is_written = False
        self.is_writing = False

        self.pipe_fd_read = self.open_pipe(filename='pipe', mode='ro')
        self.pipe_fd_write = self.open_pipe(filename='pipe', mode='wo')

    def read(self, fh):
        rlist, _, _ = select.select([self.pipe_fd], [], [], 0)
        if rlist:
            data = os.read(fh, 1024)
            if data:
                self.manager.logger.info(f"Read data from pipe: {data}")
                #process_data(data)
            else:
                self.manager.logger.info("No data available in pipe")
        return data

    def write(self, fh):
        try:
            if self.is_written == False and self.is_writing == False:
                self.manager.logger.info("calling write pipe")
                self.is_writing = True
                #response = f"{action_id},completed"
                response = "foobar"
                response_length = len(response)
                header = f"{response_length:04d}"  # Create a 4-character wide header
                os.write(fh, (header + response).encode())
                self.is_written = True
                self.is_writing = False
                self.manager.logger.info("wrote to pipe")
        except OSError as e:
            self.manager.logger.error(f"Error writing to pipe: {e}")

    def open_pipe(self, **kwargs):
        # os.join or something
        file_path = self.manager.module_path + '/' + kwargs['filename']
        self.manager.logger.info(f"attempting to open pipe at: {file_path}")

        try:
            os.mkfifo(file_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        try:
            if kwargs.get('mode') == 'ro':
                handle = os.open(file_path, os.O_RDONLY | os.O_NONBLOCK)
            elif kwargs.get('mode') == 'wo':
                handle = os.open(file_path, os.O_WRONLY | os.O_NONBLOCK)
            else:
                self.manager.logger.info("only supports ro or wo")
                return None;
            self.manager.logger.info(f"Successfully opened pipe with fd: {handle}")
            return handle
        except OSError as e:
            self.manager.logger.info(f"Failed to open pipe: {e}")
            return None;


#    def mem_test(self):
#        logger.info(sys.version_info)
#        SHM_NAME = "/my_shared_memory"
#        SHM_SIZE = 1024
#
#        # Open the shared memory
#        sys.path.append('/Users/cdeshotel/Scripts/Ableton/InterceptKeys/build/lib.macosx-13.0-x86_64-cpython-312')shm = posix_ipc.SharedMemory(SHM_NAME, posix_ipc.O_CREAT, size=SHM_SIZE)
#
#        # Map the shared memory into the address space
#        with mmap.mmap(shm.fd, SHM_SIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE) as mm:
#            # Read data from shared memory
#            data = mm[:SHM_SIZE].rstrip(b'\x00').decode('utf-8')
#            logger.info(f"Read from shared memory: {data}")
#
#            # Write data to shared memory
#            message = "Hello from Python!"
#            mm.seek(0)  # Go to the beginning of the memory
#            mm.write(message.encode('utf-8'))
#
#            data = mm[:SHM_SIZE].rstrip(b'\x00').decode('utf-8')
#            logger.info(f"Read from shared memory: {data}")
#
#        # Clean up
#        shm.close_fd()
