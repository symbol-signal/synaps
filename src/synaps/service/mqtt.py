import logging
from datetime import datetime, timezone
from typing import Dict, Any

from gmqtt import Client
from rich import json

from sensation.common import SensorId
from synaps.service.err import MissingConfigurationField, AlreadyRegistered

logger = logging.getLogger(__name__)

_brokers: Dict[str, Client] = {}

_missing_brokers = set()

REQUIRED_FIELDS = ['name', 'host']


def get_broker(broker):
    try:
        return _brokers[broker]
    except KeyError:
        raise ValueError(f"Broker {broker} not registered")


def send_device_event(broker: str, topic: str, device_id: str, event_type: str, event_data: Dict[str, Any]):
    """
    Send a device event to an MQTT broker.

    Args:
        broker: The name of the broker to send the event to
        topic: The MQTT topic to publish the event to
        device_id: The identifier for the device
        event_type: The type of event (e.g., 'relay_state_change', 'switch_state_change')
        event_data: The data specific to the event
    """
    client = _brokers.get(broker)
    if not client:
        if broker not in _missing_brokers:
            _missing_brokers.add(broker)
            logger.warning(f"[missing_mqtt_broker] broker=[{broker}]")
        return

    _missing_brokers.discard(broker)

    payload = {
        "deviceId": device_id,
        "event": event_type,
        "eventAt": datetime.now(timezone.utc).isoformat(),
        "eventData": event_data,
    }
    client.publish(topic, json.dumps(payload))
    logger.debug(f"[mqtt_device_event_published] broker=[{broker}] topic=[{topic}] payload=[{payload}]")


def on_connect(client, flags, rc, properties):
    props = client.config_x
    if rc == 0:
        logger.info(f"[mqtt_connected] broker=[{props['name']}] host=[{props['host']}]")
    else:
        logger.warning(f"[mqtt_connection_failed] broker=[{props['name']}] host=[{props['host']}]")


def on_disconnect(client, packet, exc=None):
    props = client.config_x
    logger.info(f"[mqtt_disconnected] broker=[{props['name']}] host=[{props['host']}]")


async def register(**config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config or not config[required_field]:
            raise MissingConfigurationField(required_field)

    name = config['name']
    host = config['host']

    if _brokers.get(name):
        raise AlreadyRegistered

    client = Client(client_id=name)
    client.config_x = config

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    logger.info(f"[mqtt_connecting] broker=[{name}] host=[{host}]")
    await client.connect(host=host)

    _brokers[name] = client


async def unregister_all():
    for name, client in list(_brokers.items()):
        if client.is_connected:
            logger.info(f"[disconnecting_mqtt] broker=[{name}]")
            await client.disconnect()
        del _brokers[name]
