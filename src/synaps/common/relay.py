from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RelayState(Enum):
    ON = 1
    OFF = 0


@dataclass
class RelayEvent:
    """
    Event class for relay state changes.
    The state now uses the RelayState enum for clarity.
    """
    device_id: str
    state: RelayState
    channel: Optional[str] = None

    def as_simple_value(self):
        if self.state == RelayState.ON:
            return 'ON'
        elif self.state == RelayState.OFF:
            return 'OFF'
        else:
            raise ValueError(f"Unknown relay state {self.state}")
