import logging
from datetime import datetime, timezone
from typing import Dict, Any, Callable, List, Tuple

from gmqtt import Client

from synaps.service.err import MissingConfigurationField, AlreadyRegistered

logger = logging.getLogger(__name__)

_brokers: Dict[str, Client] = {}
_pending_subscriptions: List[Tuple[str, str, Callable[[str, str], None]]] = []

_missing_brokers = set()

REQUIRED_FIELDS = ['name', 'host']


def get_broker(broker):
    try:
        return _brokers[broker]
    except KeyError:
        raise ValueError(f"Broker {broker} not registered")


def send_device_payload(broker: str, topic: str, payload: Any):
    """
    Send a device event to an MQTT broker.

    Args:
        broker: The name of the broker to send the event to
        topic: The MQTT topic to publish the event to
        payload: Payload to be sent
    """
    client = _brokers.get(broker)
    if not client:
        if broker not in _missing_brokers:
            _missing_brokers.add(broker)
            logger.warning(f"[missing_mqtt_broker] broker=[{broker}]")
        return

    _missing_brokers.discard(broker)
    client.publish(topic, payload)
    logger.debug(f"[mqtt_message_published] broker=[{broker}] topic=[{topic}] payload=[{payload}]")


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
    payload = {
        "deviceId": device_id,
        "event": event_type,
        "eventAt": datetime.now(timezone.utc).isoformat(),
        "eventData": event_data,
    }
    send_device_payload(broker, topic, payload)


def on_connect(client, flags, rc, properties):
    props = client.config_x
    if rc == 0:
        logger.info(f"[mqtt_connected] broker=[{props['name']}] host=[{props['host']}]")
    else:
        logger.warning(f"[mqtt_connection_failed] broker=[{props['name']}] host=[{props['host']}]")


def on_disconnect(client, packet, exc=None):
    props = client.config_x
    logger.info(f"[mqtt_disconnected] broker=[{props['name']}] host=[{props['host']}]")


def on_message(client, topic, payload, qos, properties):
    props = client.config_x
    broker_name = props['name']
    payload_str = payload.decode('utf-8') if isinstance(payload, bytes) else str(payload)
    logger.debug(f"[mqtt_message_received] broker=[{broker_name}] topic=[{topic}] payload=[{payload_str}]")

    handlers = props.get('_handlers', {}).get(topic, [])
    for handler in handlers:
        try:
            handler(topic, payload_str)
        except Exception as e:
            logger.error(f"[mqtt_handler_error] broker=[{broker_name}] topic=[{topic}] error=[{e}]")


def subscribe(broker: str, topic: str, handler: Callable[[str, str], None]):
    """
    Subscribe to an MQTT topic with a handler callback.

    Args:
        broker: The name of the broker to subscribe on
        topic: The MQTT topic to subscribe to
        handler: Callback function (topic, payload) -> None
    """
    client = _brokers.get(broker)
    if not client:
        _pending_subscriptions.append((broker, topic, handler))
        logger.debug(f"[mqtt_subscription_pending] broker=[{broker}] topic=[{topic}]")
        return

    _add_subscription(client, topic, handler)


def _add_subscription(client: Client, topic: str, handler: Callable[[str, str], None]):
    props = client.config_x
    if '_handlers' not in props:
        props['_handlers'] = {}

    if topic not in props['_handlers']:
        props['_handlers'][topic] = []
        client.subscribe(topic)
        logger.info(f"[mqtt_subscribed] broker=[{props['name']}] topic=[{topic}]")

    props['_handlers'][topic].append(handler)


def _process_pending_subscriptions(broker_name: str, client: Client):
    global _pending_subscriptions
    remaining = []
    for broker, topic, handler in _pending_subscriptions:
        if broker == broker_name:
            _add_subscription(client, topic, handler)
        else:
            remaining.append((broker, topic, handler))
    _pending_subscriptions = remaining


async def register(**config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config or not config[required_field]:
            raise MissingConfigurationField(required_field)

    name = config['name']
    host = config['host']

    if not config.get('enabled', True):
        logger.info("mqtt_broker_disabled name=[%s] host=[%s]", name, host)
        return

    if _brokers.get(name):
        raise AlreadyRegistered

    client = Client(client_id=name)
    client.config_x = config

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    logger.info(f"[mqtt_connecting] broker=[{name}] host=[{host}]")
    await client.connect(host=host)

    _brokers[name] = client
    _process_pending_subscriptions(name, client)


async def unregister_all():
    for name, client in list(_brokers.items()):
        if client.is_connected:
            logger.info(f"[disconnecting_mqtt] broker=[{name}]")
            await client.disconnect()
        del _brokers[name]
