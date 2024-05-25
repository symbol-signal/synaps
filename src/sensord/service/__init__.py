import logging
import signal

import tomli

from sensation.common import SensorType
from sensord.service import api, mqtt, paths, sen0395
from sensord.service.err import UnknownSensorType, MissingConfigurationField, AlreadyRegistered, InvalidConfiguration
from sensord.service.paths import ConfigFileNotFoundError

logger = logging.getLogger(__name__)


def missing_config_field(entity, field, config):
    logger.warning(f"[invalid_{entity}] reason=[missing_configuration_field] field=[{field}] config=[{config}]")


def missing_sensor_config_field(field, config):
    missing_config_field('sensor', field, config)


def missing_mqtt_config_field(field, config):
    missing_config_field('mqtt_broker', field, config)


def run():
    try:
        init_mqtt()
        init_sensors()
    except KeyboardInterrupt:
        logger.info('[exit] detail=[Initialization stage interrupted by user]')
        unregister_sensors()
        unregister_mqtt()
        return

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    api.start()


def init_sensors():
    try:
        config_file = paths.lookup_sensors_config_file()
    except ConfigFileNotFoundError as e:
        logger.warning(f"[no_sensors_config_file] detail=[{e}]")
        exit(1)

    with open(config_file, 'rb') as f:
        config = tomli.load(f)
    sensors = config.get('sensor')

    if sensors:
        register_sensors(sensors)
    else:
        logger.warning('[no_sensors_loaded] detail=[No sensors configured in the config file: %s]', config_file)


def register_sensors(sensors):
    for sensor in sensors:
        if 'type' not in sensor:
            missing_sensor_config_field('type', sensor)
            continue
        if 'name' not in sensor:
            missing_sensor_config_field('name', sensor)
            continue
        try:
            register_sensor(sensor)
            logger.info("[sensor_registered] type=[%s] name=[%s]", sensor['type'], sensor['name'])
        except MissingConfigurationField as e:
            missing_sensor_config_field(e.field, sensor)
        except InvalidConfiguration as e:
            logger.warning(f"[invalid_sensor] reason=[invalid_configuration] reason=[{e}] config=[{sensor}]")
        except UnknownSensorType as e:
            logger.warning(f"[invalid_sensor] reason=[unknown_sensor_type] type=[{e.sensor_type}] config=[{sensor}]")
        except AlreadyRegistered:
            logger.warning(f"[invalid_sensor] reason=[duplicated_sensor] type=[{sensor['type']}] config=[{sensor}]")


def register_sensor(config):
    if config["type"] == SensorType.SEN0395.value:
        sen0395.register(**config)
        return

    raise UnknownSensorType(config["type"])


def unregister_sensors():
    sen0395.unregister_all()


def init_mqtt():
    try:
        config_file = paths.lookup_mqtt_config_file()
    except ConfigFileNotFoundError:
        return

    with open(config_file, 'rb') as f:
        config = tomli.load(f)

    brokers = config.get('broker')
    if not brokers:
        return

    for broker in brokers:
        try:
            mqtt.register(**broker)
        except MissingConfigurationField as e:
            missing_sensor_config_field(e.field, broker)
        except AlreadyRegistered:
            logger.warning(f"[invalid_mqtt_broker] reason=[duplicated_broker] config=[{broker}]")


def unregister_mqtt():
    mqtt.unregister_all()


def shutdown(_, __):
    logger.info("[exit] detail=[Shutdown signal received]")
    api.stop()
    unregister_sensors()
    unregister_mqtt()
