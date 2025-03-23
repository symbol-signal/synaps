import asyncio
import logging
import signal
from asyncio import Event
from typing import Optional

import aiofiles
import rich_click as click
import tomli

from sensation.common import SensorType
from synaps import __version__
from synaps.common.socket import SocketBindException
from synaps.service import api, mqtt, sen0395, log, ws, sen0311
from synaps.common import paths
from synaps.service.cfg import Config
from synaps.service.err import UnknownSensorType, MissingConfigurationField, AlreadyRegistered, InvalidConfiguration, \
    ServiceAlreadyRunning, APINotStarted, ServiceNotStarted, ErrorDuringShutdown
from synaps.common.paths import ConfigFileNotFoundError, MQTT_CONFIG_FILE, SENSORS_CONFIG_FILE, WS_CONFIG_FILE

logger = logging.getLogger(__name__)

shutdown_event: Optional[Event] = None


def register_signal_handlers():
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, lambda: asyncio.create_task(on_signal(s)))


async def on_signal(signal_):
    logger.info(f"[exit_signal_received] signal=[{signal_.name}]")
    shutdown_event.set()


@click.command()
@click.version_option(__version__)
@click.option('--log-file-level', type=click.Choice(['debug', 'info', 'warning', 'error', 'critical', 'off']),
              default='info',
              help='Set the log level for file logging')
def cli(log_file_level):
    log.configure(True, log_file_level=log_file_level)
    logger.info('[service_started]')
    try:
        asyncio.run(run_service())
        logger.info("[service_stopped]")
    except (APINotStarted, ServiceNotStarted, ErrorDuringShutdown):
        exit(1)
    except Exception:
        logger.exception("[service_failed]")
        exit(1)


async def run_service():
    global shutdown_event
    shutdown_event = Event()

    register_signal_handlers()

    init_success = await initialize()  # Throws APINotStarted

    if init_success:
        logger.info("[service_started_successfully]")
        await shutdown_event.wait()

    shutdown_success = await shutdown()

    if not init_success:
        raise ServiceNotStarted

    if not shutdown_success:
        raise ErrorDuringShutdown


async def initialize():
    # First start API to prevent the service to run more than one instance
    await start_api()  # Raising exceptions if not started

    # Continue with init after API started successfully
    # TODO Init sensors last?
    results = await asyncio.gather(init_mqtt(), init_ws(), init_sensors(), return_exceptions=True)

    success = True
    for result in results:
        if isinstance(result, Exception):
            logger.error("[error_during_init]", exc_info=result)
            success = False

    return success


async def shutdown():
    logger.info("[shutdown_initiated]")

    success = True
    # Stop the API first before shutting down remaining of the service, so the API doesn't serve in invalid states
    try:
        await stop_api()
    except Exception:
        success = False
        logger.exception("[unexpected_stop_api_error]")

    results = await asyncio.gather(unregister_sensors(), unregister_mqtt(), unregister_ws(), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            success = False
            logger.error("[error_during_shutdown]", exc_info=result)

    return success


def missing_config_field(entity, field, config):
    logger.warning(f"[invalid_{entity}] reason=[missing_configuration_field] field=[{field}] config=[{config}]")


def missing_sensor_config_field(field, config):
    missing_config_field('sensor', field, config)


def missing_mqtt_config_field(field, config):
    missing_config_field('mqtt_broker', field, config)


async def read_config_file(filename):
    config_file = paths.lookup_file_in_config_path(filename)

    logger.info(f"[loading_config_file] file=[{config_file}]")
    async with aiofiles.open(config_file, 'rb') as f:
        content = await f.read()
    return tomli.loads(content.decode())


async def init_mqtt():
    try:
        config = await read_config_file(MQTT_CONFIG_FILE)
    except ConfigFileNotFoundError:
        return

    brokers = config.get('broker')
    if not brokers:
        return

    register_broker_tasks = [register_broker(broker) for broker in brokers]
    await asyncio.gather(*register_broker_tasks)


async def register_broker(broker):
    try:
        await mqtt.register(**broker)
    except MissingConfigurationField as e:
        missing_sensor_config_field(e.field, broker)
    except AlreadyRegistered:
        logger.warning(f"[invalid_mqtt_broker] reason=[duplicated_broker] config=[{broker}]")


async def unregister_mqtt():
    await mqtt.unregister_all()


async def init_ws():
    try:
        config = await read_config_file(WS_CONFIG_FILE)
    except ConfigFileNotFoundError:
        return

    endpoints = config.get('endpoint')
    if not endpoints:
        return

    register_client_tasks = [register_client(server) for server in endpoints]
    await asyncio.gather(*register_client_tasks)


async def register_client(server):
    try:
        await ws.register(**server)
    except MissingConfigurationField as e:
        missing_sensor_config_field(e.field, server)
    except AlreadyRegistered:
        logger.warning(f"[invalid_ws_server] reason=[duplicated_server] config=[{server}]")


async def unregister_ws():
    await ws.unregister_all()


async def init_sensors():
    try:
        config = await read_config_file(SENSORS_CONFIG_FILE)
    except ConfigFileNotFoundError as e:
        logger.warning(f"[no_sensors_config_file] detail=[{e}]")
        return

    sensors = config.get('sensor')

    if not sensors:
        logger.warning('[no_sensors_loaded] detail=[No sensors configured in the config file: %s]', SENSORS_CONFIG_FILE)
        return

    register_sensor_tasks = [register_sensor(Config('sensor', sensor_config)) for sensor_config in sensors]
    await asyncio.gather(*register_sensor_tasks)


async def register_sensor(sensor_config):
    try:
        await register_sensor_by_type(sensor_config)
        logger.info("[sensor_registered] type=[%s] name=[%s]", sensor_config['type'], sensor_config['name'])
    except MissingConfigurationField as e:
        missing_sensor_config_field(e.field, sensor_config)
    except InvalidConfiguration as e:
        logger.warning(f"[invalid_sensor] reason=[invalid_configuration] reason=[{e}] config=[{sensor_config}]")
    except UnknownSensorType as e:
        logger.warning(f"[invalid_sensor] reason=[unknown_sensor_type] type=[{e.sensor_type}] config=[{sensor_config}]")
    except AlreadyRegistered:
        logger.warning(f"[invalid_sensor] reason=[duplicated_sensor] type=[{sensor_config['type']}] config=[{sensor_config}]")


async def register_sensor_by_type(sensor_config):
    if sensor_config["type"] == SensorType.SEN0395.value:
        await sen0395.register(sensor_config)
        return
    if sensor_config["type"] == SensorType.SEN0311.value:
        await sen0311.register(sensor_config)
        return

    raise UnknownSensorType(sensor_config["type"])


async def unregister_sensors():
    await sen0395.unregister_all()
    await sen0311.unregister_all()


async def start_api():
    try:
        await api.start()
    except SocketBindException as e:
        logger.error(f"[socket_bind_error] result=[exiting] reason=[{e}] check=[Is the service already running?]")
        print(f"You can try removing `{paths.API_SOCKET}` if you are absolutely sure the service is not running.")
        raise APINotStarted
    except ServiceAlreadyRunning:
        logger.warning("[service_is_already_running] result=[exiting]")
        raise APINotStarted
    except PermissionError as e:
        logger.warning(f"[socket_permission_error] detail=[{e}] result=[exiting]")
        print("The service runs restricted under different user. "
              f"You can try removing `{paths.API_SOCKET}` if you are absolutely sure the service is not running.")
        raise APINotStarted


async def stop_api():
    try:
        await api.stop()
    except Exception:
        logger.exception("[unexpected_api_stop_error]")
