import logging
from datetime import datetime, timezone
from typing import Dict

from gmqtt import Client
from rich import json

from sensation.common import SensorId
from sensord.service.err import MissingConfigurationField, AlreadyRegistered

logger = logging.getLogger(__name__)

_brokers: Dict[str, Client] = {}

_missing_brokers = set()

REQUIRED_FIELDS = ['name', 'host']


def get_broker(broker):
    try:
        return _brokers[broker]
    except KeyError:
        raise ValueError(f"Broker {broker} not registered")


def send_presence_changed_event(broker: str, topic: str, sensor_id: SensorId, presence: bool):
    client = _brokers.get(broker)
    if not client:
        if broker not in _missing_brokers:
            _missing_brokers.add(broker)  # Keep record of missing brokers so we log the warning below only once
            logger.warning(f"[missing_mqtt_broker] broker=[{broker}]")
        return

    _missing_brokers.discard(broker)

    payload = {
        "sensorId": f"{sensor_id.sensor_type.value}/{sensor_id.sensor_name}",
        "event": "presence_change",
        "eventAt": datetime.now(timezone.utc).isoformat(),
        "eventData": {"presence": presence},
    }
    client.publish(topic, json.dumps(payload))
    logger.debug(f"[mqtt_message_published] broker=[{broker}] message=[{payload}]")


def on_connect(_, userdata, __, rc):
    if rc == 0:
        logger.info(f"[mqtt_connected] broker=[{userdata['name']}] host=[{userdata['host']}]")
    else:
        logger.warning(f"[mqtt_connection_failed] broker=[{userdata['name']}] host=[{userdata['host']}]")


def on_disconnect(_, userdata, rc):
    if rc == 0:
        logger.info(f"[mqtt_disconnected] broker=[{userdata['name']}] host=[{userdata['host']}]")
    else:
        logger.warning(
            f"[mqtt_disconnected_unexpectedly] broker=[{userdata['name']} host=[{userdata['host']}]] return code={rc}")


async def register(**config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config or not config[required_field]:
            raise MissingConfigurationField(required_field)

    name = config['name']
    host = config['host']

    if _brokers.get(name):
        raise AlreadyRegistered

    client = Client(client_id=name)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    await client.connect(host=host)

    _brokers[name] = client


async def unregister_all():
    for name, client in list(_brokers.items()):
        await client.disconnect()
        del _brokers[name]
