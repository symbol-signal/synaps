import asyncio
import logging
import time
from abc import ABC
from typing import Optional, Union, List, Iterable, Awaitable

from gpiozero import Button, OutputDevice

from synaps.common.relay import RelayState, RelayEvent
from synaps.common.switch import SwitchEvent, SwitchState

log = logging.getLogger(__name__)


class InputSwitch:

    def __init__(self, device_id, button: Button):
        self.button = button
        self.device_id = device_id
        self.observers = []
        self.event_loop = asyncio.get_running_loop()
        self.button.when_pressed = self._on_pressed
        self.button.when_released = self._on_released

    def add_observer(self, callback):
        self.observers.append(callback)

    def remove_observer(self, callback):
        self.observers.remove(callback)

    def _on_pressed(self):
        event = SwitchEvent(self.device_id, SwitchState.PRESSED)
        for observer in self.observers:
            result = observer(event)
            if isinstance(result, Awaitable):
                asyncio.run_coroutine_threadsafe(result, self.event_loop)

    def _on_released(self):
        event = SwitchEvent(self.device_id, SwitchState.RELEASED)
        for observer in self.observers:
            result = observer(event)
            if isinstance(result, Awaitable):
                asyncio.run_coroutine_threadsafe(result, self.event_loop)

    def close(self):
        self.button.close()


class OutputRelay:
    """
    Represents a relay on the Kincony Server-Mini.
    Now uses RelayState enum for state management and includes a
    cooldown to prevent rapid toggling.
    """

    def __init__(self, device_id: str, output_device: OutputDevice,
                 *, initial_state: Optional[bool] = None, toggle_cooldown: float = 0.5):
        self.device_id = device_id
        self.output_device = output_device
        self.observers = []
        self.event_loop = asyncio.get_running_loop()
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

    def __call__(self, e: SwitchEvent):
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
            log.warning(f"[relay_toggle_ignored] device=[{self.device_id}] reason=[toggle_in_cooldown]")
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
        event = RelayEvent(self.device_id, state)
        for observer in self.observers:
            result = observer(event)
            if isinstance(result, Awaitable):
                asyncio.run_coroutine_threadsafe(result, self.event_loop)

    def close(self):
        """Clean up resources."""
        self.output_device.close()


def link_switch_to_relay(switch: InputSwitch, relays: Iterable[OutputRelay], toggle_state: SwitchState):
    def observer(e: SwitchEvent):
        if e.switch_state == toggle_state:
            for relay in relays:
                relay.toggle()

    switch.add_observer(observer)


class RpioPlatform(ABC):

    def __init__(self, switches: List[InputSwitch], relays: List[OutputRelay]):
        self.switches = switches
        self.relays = relays

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
