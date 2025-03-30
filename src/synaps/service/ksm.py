import logging
from enum import Enum
from typing import List, Union

from gpiozero import Button, OutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

from synaps.common.switch import SwitchState
from synaps.service import mqtt, ws
from synaps.service.cfg import Config
from synaps.service.err import InvalidConfiguration
from synaps.service.rpio import RpioPlatform, InputSwitch, OutputRelay, link_switch_to_relay

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


class KinconyServerMini(RpioPlatform):

    def __init__(self, pin_factory, switches: List[InputSwitch], relays: List[OutputRelay]):
        super().__init__(switches, relays)
        self.pin_factory = pin_factory

    @property
    def host(self):
        return self.pin_factory.host

    def close(self):
        super().close()
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


def create_relays(factory: PiGPIOFactory, platform_config: Config) -> List[OutputRelay]:
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
        relay = OutputRelay(device_id, output_device, initial_state=relay_conf.get("initial_state"))
        relays.append(relay)

        for mc in (platform_config.get_list("mqtt") + relay_conf.get_list("mqtt")):
            broker = mc['broker']
            topic = mc['topic']
            relay.add_observer(
                lambda event, b=broker, t=topic, d=device_id:
                mqtt.send_device_event(b, t, d, "relay_state_change", {"state": event.state.name.lower()})
            )

        for wc in (platform_config.get_list("ws") + relay_conf.get_list("ws")):
            endpoint = wc['endpoint']
            relay.add_observer(
                lambda event, e=endpoint, d=device_id:
                ws.send_device_event(e, d, "relay_state_change", {"state": event.state.name.lower()})
            )

    return relays


def create_switches(factory, conf, relays: List[OutputRelay]):
    device_to_relay = {r.device_id: r for r in relays}
    switches = []
    bounce_time = None

    if global_switch_conf := conf.get("switches", None):
        bounce_time = global_switch_conf.get("bounce_time", None)

    for switch_conf in conf.get_list("switch"):
        di = DigitalInput.get_by_id(switch_conf["digital_input"])
        dev_id = switch_conf["device_id"]
        button = Button(pin=di.gpio_pin, pin_factory=factory, bounce_time=bounce_time or switch_conf.get("bounce_time"))
        switch = InputSwitch(dev_id, button)
        switches.append(switch)

        for mc in (conf.get_list("mqtt") + switch_conf.get_list("mqtt")):
            broker = mc['broker']
            topic = mc['topic']
            switch.add_observer(
                lambda event, b=broker, t=topic, d=dev_id:
                mqtt.send_device_event(b, t, d, "switch_state_change", event.serialize())
            )

        for wc in (conf.get_list("ws") + switch_conf.get_list("ws")):
            endpoint = wc['endpoint']
            switch.add_observer(
                lambda event, e=endpoint, d=dev_id:
                ws.send_device_event(e, d, "switch_state_change", event.serialize())
            )

        for rlink_conf in switch_conf.get_list("relay_link"):
            toggle_on_str = rlink_conf.get("toggle_on", SwitchState.RELEASED.name)
            try:
                toggle_state = SwitchState[toggle_on_str.upper()]
            except KeyError:
                valid_states = ", ".join(state.name.lower() for state in SwitchState)
                raise InvalidConfiguration(f"Invalid state value `{toggle_on_str}`, valid: `{valid_states}`")
            matching_relay = device_to_relay[rlink_conf["device"]]
            if not matching_relay:
                raise InvalidConfiguration(f'Linked relay devices not found: `{rlink_conf["device"]}`')

            link_switch_to_relay(switch, [matching_relay], toggle_state)

    return switches


def unregister_all():
    for host, platform in list(_servers.items()):
        platform.close()
        del _servers[host]
