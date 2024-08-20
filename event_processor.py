import Live
from ableton.v2.control_surface.component import Component
import logging

class EventProcessor(Component):
    def __init__(self, manager):
        super().__init__(manager)
        pass
    
    def tick(self):
        """
        Called once per 100ms "tick".
        """
        self.manager.logger.info("Tick...")
