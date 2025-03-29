from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class SwitchState(Enum):
    PRESSED = auto()
    RELEASED = auto()


@dataclass
class SwitchEvent:
    device_id: str
    switch_state: SwitchState
    switch_id: Optional[str] = None

    def serialize(self) -> dict:
        return {
            "device_id": self.device_id,
            "switch_state": self.switch_state.name.lower(),
            "switch_id": self.switch_id,
        }