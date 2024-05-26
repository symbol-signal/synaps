import logging
from typing import List, Optional

from serial import Serial

from sensation.sen0395 import Sensor, PresenceHandler
from sensord.service import mqtt
from sensord.service.err import AlreadyRegistered, MissingConfigurationField, InvalidConfiguration

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ['port']

_sensors = {}


def register(**config):
    validate_config(config)

    if _sensors.get(config['name']):
        raise AlreadyRegistered

    sensor = _init_sensor(config)
    _sensors[config['name']] = sensor


def validate_config(config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config:
            raise MissingConfigurationField(required_field)
    if mqtt_brokers := config.get('mqtt'):
        if not isinstance(mqtt_brokers, list):
            raise InvalidConfiguration("`mqtt` field must be a list")

        for broker_config in mqtt_brokers:
            if 'broker' not in broker_config:
                raise MissingConfigurationField('mqtt.broker')
            if 'topic' not in broker_config:
                raise MissingConfigurationField('mqtt.topic')

def _init_sensor(config):
    s = Sensor(config['name'], Serial(config['port'], 115200, timeout=1))
    handler = PresenceHandler()
    s.handlers.append(handler)

    if config.get('print_presence'):
        handler.observers.append(
            lambda presence: log.debug(f"[presence_change] sensor=[{s.sensor_id}] presence=[{presence}]"))

    if mqtt_brokers := config.get("mqtt"):
        for conf in mqtt_brokers:
            handler.observers.append(
                lambda presence: mqtt.send_presence_changed_event(conf['broker'], conf['topic'], s.sensor_id, presence))

    if config.get('enabled'):
        s.start_reading()

    if config.get('autostart'):
        scanning = s.read_presence() is not None
        if scanning:
            log.info(f"[autostart] sensor=[{s.sensor_id}] result=[already_scanning]")
        else:
            resp = s.start_scanning()
            if resp:
                log.info(f"[autostart] sensor=[{s.sensor_id}] result=[started]")
            else:
                log.warning(f"[autostart] sensor=[{s.sensor_id}] result=[failed] response=[{resp}]")

    return s

def get_all_sensors() -> List[Sensor]:
    return list(_sensors.values())


def get_sensor(name) -> Optional[Sensor]:
    return _sensors.get(name)


def unregister_all():
    for name, sensor in list(_sensors.items()):
        sensor.close()
        del _sensors[name]
