import logging
from typing import List, Optional

import serialio

from sensation.sen0311 import SensorAsync, PresenceHandlerAsync
from synaps.service import mqtt, ws
from synaps.service.err import AlreadyRegistered

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

    # Total max delay for presence change trigger => 0.5 * (hysteresis_count - 1)
    read_sleep_interval = 0.5  # TODO config parameter

    if presence := config.get('presence'):
        handler = PresenceHandlerAsync(
            threshold_presence=presence['threshold_presence'],
            threshold_absence=presence['threshold_absence'],
            hysteresis_count=presence.get('hysteresis_count', 1),
            delay_presence=presence.get('delay_presence', 0),
            delay_absence=presence.get('delay_absence', 0),
        )
        s.handlers.append(handler)

        if presence.get('log_events'):
            handler.observers.append(
                lambda presence_val: log.info(f"[sen0311_presence_change] sensor=[{s.sensor_id}] presence=[{presence_val}]"))

        for mc in presence.get_list("mqtt"):
            broker = mc['broker']
            topic = mc['topic']
            handler.observers.append(
                lambda presence_val, b=broker, t=topic:
                mqtt.send_device_event(b, t, str(s.sensor_id), "presence_change", {"presence": presence_val})
            )

        for wc in presence.get_list("ws"):
            endpoint = wc['endpoint']
            handler.observers.append(
                lambda presence_val, e=endpoint:
                ws.send_device_event(e, str(s.sensor_id), "presence_change", {"presence": presence_val}))

    # TODO Handling exceptions from start methods to not prevent registration
    if config.get('enabled'):
        s.start_reading(read_sleep_interval)

    return s


def get_all_sensors() -> List[SensorAsync]:
    return list(_sensors.values())


def get_sensor(name) -> Optional[SensorAsync]:
    return _sensors.get(name)


async def unregister_all():
    for name, sensor in list(_sensors.items()):
        await sensor.close()
        del _sensors[name]
