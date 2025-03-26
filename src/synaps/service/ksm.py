import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Union

from gpiozero import Button
from gpiozero.pins.pigpio import PiGPIOFactory

from synaps.common.switch import SwitchState
from synaps.service.err import InvalidConfiguration
from synaps.service.cfg import Config
from synaps.service.rpio import RpioPlatform

KINCONY_SERVER_MINI = 'KINCONY_SERVER_MINI'

log = logging.getLogger(__name__)


class DigitalInput(Enum):
    """
    Enumeration of digital inputs on the Kincony Server-Mini.
    Each enum value represents a digital input port with its corresponding GPIO pin number.
    Format: (input_id, gpio_pin)
    """
    DIGITAL_INPUT_1 = (1, 18)
    DIGITAL_INPUT_2 = (2, 23)
    DIGITAL_INPUT_3 = (3, 24)
    DIGITAL_INPUT_4 = (4, 25)
    DIGITAL_INPUT_5 = (5, 12)
    DIGITAL_INPUT_6 = (6, 16)
    DIGITAL_INPUT_7 = (7, 20)
    DIGITAL_INPUT_8 = (8, 21)

    def __init__(self, input_id: int, gpio_pin: int):
        self.input_id = input_id
        self.gpio_pin = gpio_pin

    @classmethod
    def get_by_id(cls, input_id: Union[int, str]) -> 'DigitalInput':
        """
        Get a digital input by its ID. Supports both string and integer IDs.

        Args:
            input_id: The ID of the input, can be either an integer (1) or string ("1")

        Returns:
            The DigitalInput enum value if found

        Raises:
            InvalidConfiguration: If input_id is invalid or out of range
        """
        # Convert string input_id to integer if needed
        if isinstance(input_id, str):
            try:
                input_id = int(input_id)
            except ValueError:
                raise InvalidConfiguration(
                    f"platform.switch.digital_input value `{input_id}` cannot be converted to integer")

        # Try to get the enum value by input_id
        for input_enum in cls:
            if input_enum.input_id == input_id:
                return input_enum

        raise InvalidConfiguration(
            f"platform.switch.digital_input value `{input_id}` is not between 1-8")


def create_platform(platform_config: Config):
    host = platform_config["host"]
    factory = PiGPIOFactory(host=host)

    switches = []
    for switch_conf in platform_config.get_list("switch"):
        di = DigitalInput.get_by_id(switch_conf["digital_input"])
        dev_id = switch_conf["device_id"]
        button = Button(pin=di.gpio_pin, pin_factory=factory)
        switch = KsmSwitch(button, di, dev_id)
        switches.append(switch)

    platform = KinconyServerMini(factory, switches)

    if platform_config.get("print_state"):
        platform.add_observer_switches(lambda e: print(e))

    return platform


@dataclass
class KsmSwitchEvent:
    digital_input: DigitalInput
    device_id: str
    switch_state: SwitchState


class KsmSwitch:

    def __init__(self, button: Button, digital_input: DigitalInput, device_id):
        self.button = button
        self.digital_input = digital_input
        self.device_id = device_id
        self.observers = []
        self.button.when_pressed = self._on_pressed
        self.button.when_released = self._on_released

    def add_observer(self, callback):
        self.observers.append(callback)

    def remove_observer(self, callback):
        self.observers.remove(callback)

    def _on_pressed(self):
        event = KsmSwitchEvent(self.digital_input, self.device_id, SwitchState.PRESSED)
        for observer in self.observers:
            observer(event)

    def _on_released(self):
        event = KsmSwitchEvent(self.digital_input, self.device_id, SwitchState.RELEASED)
        for observer in self.observers:
            observer(event)

    def close(self):
        self.button.close()


class KinconyServerMini(RpioPlatform):

    def __init__(self, pin_factory, switches: List[KsmSwitch]):
        self.pin_factory = pin_factory
        self.switches = switches

    def add_observer_switches(self, callback):
        for switch in self.switches:
            switch.add_observer(callback)

    def remove_observer_switches(self, callback):
        for switch in self.switches:
            switch.remove_observer(callback)

    def close(self):
        for switch in self.switches:
            switch.close()
        self.pin_factory.close()
