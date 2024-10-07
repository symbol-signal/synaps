import logging
from typing import List, Optional

import serialio

from sensation.sen0311 import SensorAsync, PresenceHandlerAsync
from sensord.service import mqtt, ws
from sensord.service.err import AlreadyRegistered

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ['port']

_sensors = {}


async def register(config):
    if _sensors.get(config['name']):
        raise AlreadyRegistered

    sensor = await _init_sensor(config)
    _sensors[config['name']] = sensor


async def _init_sensor(config):
    serial_con = serialio.serial_for_url(config['port'], 9600, timeout=1)
    serial_con.host = 'fake'
    s = SensorAsync(config['name'], serial_con)
    await serial_con.open()

    handler = PresenceHandlerAsync(100, 1000, 2)
    s.handlers.append(handler)

    if config.get('print_presence'):
        handler.observers.append(
            lambda presence: log.debug(f"[presence_change] sensor=[{s.sensor_id}] presence=[{presence}]"))

    for mc in config.get_list("mqtt"):
        handler.observers.append(
            lambda presence: mqtt.send_presence_changed_event(mc['broker'], mc['topic'], s.sensor_id, presence))

    for wc in config.get_list("ws"):
        handler.observers.append(
            lambda presence: ws.send_presence_changed_event(wc['endpoint'], s.sensor_id, presence))

    # TODO Handling exceptions from start methods to not prevent registration
    if config.get('enabled'):
        s.start_reading(0.5)

    return s


def get_all_sensors() -> List[SensorAsync]:
    return list(_sensors.values())


def get_sensor(name) -> Optional[SensorAsync]:
    return _sensors.get(name)


async def unregister_all():
    for name, sensor in list(_sensors.items()):
        await sensor.close()
        del _sensors[name]
