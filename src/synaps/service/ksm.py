import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Union, Optional

from gpiozero import Button, OutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

from synaps.common.relay import RelayState
from synaps.common.switch import SwitchState
from synaps.service.err import InvalidConfiguration
from synaps.service.cfg import Config
from synaps.service.rpio import RpioPlatform
from synaps.service import mqtt, ws

log = logging.getLogger(__name__)

KINCONY_SERVER_MINI = 'KINCONY_SERVER_MINI'

_servers = {}


def register(platform_config):
    kincony_server_mini = create_platform(platform_config)
    _servers[kincony_server_mini.host] = kincony_server_mini


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


@dataclass
class KsmSwitchEvent:
    digital_input: DigitalInput
    device_id: str
    switch_state: SwitchState


class KsmSwitch:

    def __init__(self, digital_input: DigitalInput, device_id, button: Button):
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


class RelayChannel(Enum):
    """
    Enumeration of relay outputs on the Kincony Server-Mini.
    Each enum value represents a relay output with its corresponding GPIO pin number.
    Format: (relay_id, gpio_pin)
    """
    RELAY_1 = (1, 5)
    RELAY_2 = (2, 22)
    RELAY_3 = (3, 17)
    RELAY_4 = (4, 4)
    RELAY_5 = (5, 6)
    RELAY_6 = (6, 13)
    RELAY_7 = (7, 19)
    RELAY_8 = (8, 26)

    def __init__(self, channel_number: int, gpio_pin: int):
        self.channel_number = channel_number
        self.gpio_pin = gpio_pin

    @classmethod
    def get_by_channel_number(cls, channel_number: Union[int, str]) -> 'RelayChannel':
        """
        Get a relay by its ID. Supports both string and integer IDs.

        Args:
            channel_number: The ID of the relay, can be either an integer (1) or string ("1")

        Returns:
            The Relay enum value if found

        Raises:
            InvalidConfiguration: If relay_id is invalid or out of range
        """
        if isinstance(channel_number, str):
            try:
                channel_number = int(channel_number)
            except ValueError:
                raise InvalidConfiguration(
                    f"platform.relay.relay_channel value `{channel_number}` cannot be converted to integer")

        for relay_enum in cls:
            if relay_enum.channel_number == channel_number:
                return relay_enum

        raise InvalidConfiguration(f"platform.relay.relay_channel value `{channel_number}` is not between 1-8")


@dataclass
class KsmRelayEvent:
    """
    Event class for relay state changes.
    The state now uses the RelayState enum for clarity.
    """
    channel: RelayChannel
    device_id: str
    state: RelayState


class KsmRelay:
    """
    Represents a relay on the Kincony Server-Mini.
    Now uses RelayState enum for state management and includes a
    cooldown to prevent rapid toggling.
    """

    def __init__(self, channel: RelayChannel, device_id: str, output_device: OutputDevice,
                 initial_state: Optional[bool] = None, toggle_cooldown: float = 0.5):
        self.channel = channel
        self.device_id = device_id
        self.output_device = output_device
        self.observers = []
        self._toggle_cooldown = toggle_cooldown
        self._last_toggle_time = 0.0

        if initial_state is not None:
            self.set_state(initial_state)

    def add_observer(self, callback):
        """Add an observer callback that will be called when the relay state changes."""
        self.observers.append(callback)

    def remove_observer(self, callback):
        """Remove an observer callback."""
        self.observers.remove(callback)

    def __call__(self, e: KsmSwitchEvent):
        if e.switch_state == SwitchState.PRESSED:
            self.toggle()

    def set_state(self, state: Union[bool, RelayState]):
        """
        Set the relay state.
        Accepts either a boolean or a RelayState enum.
        """
        # Convert boolean to RelayState if needed.
        if isinstance(state, bool):
            state = RelayState.ON if state else RelayState.OFF

        if state == RelayState.ON:
            self.output_device.on()
        else:
            self.output_device.off()

        # Notify observers with the RelayState enum.
        self._notify_observers(state)

    def turn_on(self):
        """Turn on the relay."""
        self.set_state(RelayState.ON)

    def turn_off(self):
        """Turn off the relay."""
        self.set_state(RelayState.OFF)

    def toggle(self):
        """Toggle the relay state, but only if the cooldown has elapsed."""
        current_time = time.time()
        if current_time - self._last_toggle_time < self._toggle_cooldown:
            log.warning(f"[relay_toggle_ignored] relay=[{self.channel}] reason=[toggle_in_cooldown]")
            return

        self._last_toggle_time = current_time
        self.output_device.toggle()
        # Determine the new state based on output device value.
        new_state = RelayState.ON if self.output_device.value == 1 else RelayState.OFF
        self._notify_observers(new_state)

    def get_state(self) -> RelayState:
        """Get the current state of the relay as a RelayState enum."""
        return RelayState.ON if self.output_device.value == 1 else RelayState.OFF

    def _notify_observers(self, state: RelayState):
        """Notify all observers about the relay state change."""
        event = KsmRelayEvent(self.channel, self.device_id, state)
        for observer in self.observers:
            observer(event)

    def close(self):
        """Clean up resources."""
        self.output_device.close()


class KinconyServerMini(RpioPlatform):

    def __init__(self, pin_factory, switches: List[KsmSwitch], relays: List[KsmRelay]):
        self.pin_factory = pin_factory
        self.switches = switches
        self.relays = relays

    @property
    def host(self):
        return self.pin_factory.host

    def add_observer_switches(self, callback):
        for switch in self.switches:
            switch.add_observer(callback)

    def remove_observer_switches(self, callback):
        for switch in self.switches:
            switch.remove_observer(callback)

    def close(self):
        for switch in self.switches:
            switch.close()
        for relay in self.relays:
            relay.close()

        self.pin_factory.close()


def create_platform(conf: Config):
    host = conf["host"]
    factory = PiGPIOFactory(host=host)

    relays = create_relays(factory, conf)
    switches = create_switches(factory, conf, relays)

    platform = KinconyServerMini(factory, switches, relays)

    if conf.get("log_events"):
        platform.add_observer_switches(lambda e: log.info(f"[ksm_event] host=[{platform.host}] event=[e]"))

    return platform


def create_relays(factory: PiGPIOFactory, platform_config: Config) -> List[KsmRelay]:
    """
    Create relay objects based on configuration and add them to the platform

    Args:
        platform_config: Configuration object containing relay settings
        factory: PiGPIOFactory for creating output devices

    Returns:
        List of created KsmRelay objects
    """
    relays = []

    for relay_conf in platform_config.get_list("relay"):
        relay_ch = RelayChannel.get_by_channel_number(relay_conf["channel"])
        device_id = relay_conf["device_id"]
        output_device = OutputDevice(
            pin=relay_ch.gpio_pin,
            pin_factory=factory,
            active_high=relay_conf.get("active_high", True),
            initial_value=relay_conf.get("initial_state", False)
        )
        relay = KsmRelay(relay_ch, device_id, output_device, initial_state=relay_conf.get("initial_state"))
        relays.append(relay)

        for mc in (platform_config.get_list("mqtt") + relay_conf.get_list("mqtt")):
            broker = mc['broker']
            topic = mc['topic']
            relay.add_observer(
                lambda event, b=broker, t=topic, d=device_id:
                mqtt.send_device_event(b, t, d, "relay_state_change",
                                       {"eventData": {"state": event.state.name.lower()}})
            )

        for wc in (platform_config.get_list("ws") + relay_conf.get_list("ws")):
            endpoint = wc['endpoint']
            relay.add_observer(
                lambda event, e=endpoint, d=device_id:
                ws.send_device_event(e, d, "relay_state_change",
                                     {"state": event.state.name.lower()})
            )

    return relays


def create_switches(factory, conf, relays: List[KsmRelay]):
    channel_to_relay = {r.channel: r for r in relays}

    switches = []
    bounce_time = conf.get("switch_bounce_time")
    for switch_conf in conf.get_list("switch"):
        di = DigitalInput.get_by_id(switch_conf["digital_input"])
        dev_id = switch_conf["device_id"]
        button = Button(pin=di.gpio_pin, pin_factory=factory, bounce_time=bounce_time or switch_conf.get("bounce_time"))
        switch = KsmSwitch(di, dev_id, button)
        switches.append(switch)

        for mc in (conf.get_list("mqtt") + switch_conf.get_list("mqtt")):
            broker = mc['broker']
            topic = mc['topic']
            switch.add_observer(
                lambda event, b=broker, t=topic, d=dev_id:
                mqtt.send_device_event(b, t, d, "switch_state_change",
                                       {"eventData": {"state": event.switch_state.name.lower()}})
            )

        for wc in (conf.get_list("ws") + switch_conf.get_list("ws")):
            endpoint = wc['endpoint']
            switch.add_observer(
                lambda event, e=endpoint, d=dev_id:
                ws.send_device_event(e, d, "switch_state_change",
                                     {"state": event.switch_state.name.lower()})
            )

        for toggle_relay in switch_conf.get_list("toggle_relays"):
            relay_channel = RelayChannel.get_by_channel_number(toggle_relay)
            relay = channel_to_relay.get(relay_channel)
            if relay is None:
                raise InvalidConfiguration(
                    f"Invalid relay wiring of switch `{di}`: relay {relay_channel} is not configured")
            switch.add_observer(relay)

    return switches


def unregister_all():
    for host, platform in list(_servers.items()):
        platform.close()
        del _servers[host]
