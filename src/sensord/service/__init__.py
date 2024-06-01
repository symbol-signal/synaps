import logging
import signal

import rich_click as click
import tomli

from sensation.common import SensorType
from sensord.common.socket import SocketBindException
from sensord.service import api, mqtt, paths, sen0395, log
from sensord.service.err import UnknownSensorType, MissingConfigurationField, AlreadyRegistered, InvalidConfiguration, \
    ServiceAlreadyRunning
from sensord.service.paths import ConfigFileNotFoundError

logger = logging.getLogger(__name__)


@click.command()
@click.option('--log-file-level', type=click.Choice(['debug', 'info', 'warning', 'error', 'critical', 'off']), default='info',
              help='Set the log level for file logging')
def cli(log_file_level):
    log.configure(True, log_file_level=log_file_level)

    try:
        run()
    except KeyboardInterrupt:
        logger.info('[service_exit] detail=[Initialization stage interrupted by user]')
        shutdown()
    except Exception:
        logger.exception("[unexpected_error]")
        shutdown()
        raise


def missing_config_field(entity, field, config):
    logger.warning(f"[invalid_{entity}] reason=[missing_configuration_field] field=[{field}] config=[{config}]")


def missing_sensor_config_field(field, config):
    missing_config_field('sensor', field, config)


def missing_mqtt_config_field(field, config):
    missing_config_field('mqtt_broker', field, config)


def run():
    logger.info('[service_started]')
    try:
        api.start()
    except SocketBindException as e:
        logger.error(f"[socket_bind_error] reason=[{e}] check=[Is the service already running?]")
        print(f"You can try removing `{paths.API_SOCKET}` if you are absolutely sure the service is not running.")
        exit(1)
    except ServiceAlreadyRunning:
        logger.warning("[service_is_already_running] result=[exiting]")
        exit(1)
    except PermissionError as e:
        logger.warning(f"[socket_permission_error] detail=[{e}] result=[exiting]")
        print("The service runs restricted under different user. "
              f"You can try removing `{paths.API_SOCKET}` if you are absolutely sure the service is not running.")
        exit(1)

    init_mqtt()
    init_sensors()

    signal.signal(signal.SIGTERM, signal_shutdown)
    signal.signal(signal.SIGINT, signal_shutdown)


def init_sensors():
    try:
        config_file = paths.lookup_sensors_config_file()
    except ConfigFileNotFoundError as e:
        logger.warning(f"[no_sensors_config_file] detail=[{e}]")
        return

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


def signal_shutdown(_, __):
    logger.info("[exit_signal_received]")
    shutdown()
    logger.info("[service_exited] reason=[signal]")


def shutdown():
    api.stop()
    unregister_sensors()
    unregister_mqtt()
