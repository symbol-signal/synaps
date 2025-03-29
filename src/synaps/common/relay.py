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
