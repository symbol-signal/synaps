import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict

import websockets
from rich import json

from sensation.common import SensorId
from sensord.service.err import MissingConfigurationField, AlreadyRegistered

logger = logging.getLogger(__name__)

_servers: Dict[str, websockets.WebSocketClientProtocol] = {}

_missing_servers = set()

REQUIRED_FIELDS = ['name', 'uri']


def get_server(name):
    try:
        return _servers[name]
    except KeyError:
        raise ValueError(f"Server {name} not registered")


async def send_presence_changed_event(name: str, sensor_id: SensorId, presence: bool):
    server = _servers.get(name)
    if not server:
        if name not in _missing_servers:
            _missing_servers.add(name)
            logger.warning(f"[missing_websocket_server] name=[{name}]")
        return

    _missing_servers.discard(name)

    payload = {
        "sensorId": f"{sensor_id.sensor_type.value}/{sensor_id.sensor_name}",
        "event": "presence_change",
        "eventAt": datetime.now(timezone.utc).isoformat(),
        "eventData": {"presence": presence},
    }
    await server.send(json.dumps(payload))
    logger.debug(f"[websocket_message_sent] server=[{name}] message=[{payload}]")


async def handle_connection(name: str, uri: str):
    logger.info(f"[websocket_connecting] server=[{name}] uri=[{uri}]")
    async for websocket in websockets.connect(uri):
        logger.debug(f"[websocket_connected] server=[{name}] uri=[{uri}]")
        _servers[name] = websocket

        try:
            async for message in websocket:
                logger.debug(f"[websocket_message_received] server=[{name}] message=[{message}]")

        except websockets.ConnectionClosed:
            logger.info(f"[websocket_disconnected] server=[{name}] uri=[{uri}]")
            if name not in _servers:
                # This logic relies on a rule that the server is removed from the servers before it is closed
                break

        logger.info(f"[websocket_reconnecting] server=[{name}] uri=[{uri}]")


async def register(**config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config or not config[required_field]:
            raise MissingConfigurationField(required_field)

    name = config['name']
    uri = config['uri']

    if _servers.get(name):
        raise AlreadyRegistered

    await asyncio.create_task(handle_connection(name, uri))


async def unregister_all():
    for name, server in list(_servers.items()):
        # Always delete the server first before closing, see #handle_connection() for details
        del _servers[name]
        if not server.closed:
            logger.info(f"[closing_websocket_connection] server=[{name}]")
            await server.close()
