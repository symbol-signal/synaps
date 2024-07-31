import logging
import asyncio
from asyncio import Task
from datetime import datetime, timezone
from typing import Dict, Set, Tuple

import websockets
from rich import json

from sensation.common import SensorId
from sensord.service.err import MissingConfigurationField, AlreadyRegistered

logger = logging.getLogger(__name__)

_clients: Dict[str, Tuple['WSClient', Task]] = {}

_missing_servers: Set[str] = set()

REQUIRED_FIELDS = ['name', 'uri']


def get_client(server_name) -> 'WSClient':
    try:
        return _clients[server_name][0]
    except KeyError:
        raise ValueError(f"Client for {server_name} server not registered")


class WSClient:
    def __init__(self, name: str, uri: str):
        self.name = name
        self.uri = uri
        self.websocket = None
        self.closed = False
        self.connected_event = asyncio.Event()

    async def handle_connection(self):
        logger.info(f"[websocket_connecting] server=[{self.name}] uri=[{self.uri}]")
        async for websocket in websockets.connect(self.uri):
            logger.info(f"[websocket_connected] server=[{self.name}] uri=[{self.uri}]")
            self.websocket = websocket
            self.connected_event.set()

            try:
                await self.print_message_loop()
            except websockets.ConnectionClosed:
                logger.info(f"[websocket_disconnected] server=[{self.name}] uri=[{self.uri}]")
                if self.closed:
                    return

            logger.info(f"[websocket_reconnecting] server=[{self.name}] uri=[{self.uri}]")
            self.connected_event.clear()
            self.websocket = None

    async def wait_connected(self, timeout):
        try:
            await asyncio.wait_for(self.connected_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def print_message_loop(self):
        async for message in self.websocket:
            logger.debug(f"[websocket_message_received] server=[{self.name}] message=[{message}]")

    async def send_message(self, message, timeout=None):
        if timeout:
            await self.wait_connected(timeout)
        if self.websocket:
            await self.websocket.send(message)
        else:
            logger.info(f"[websocket_message_unsent] reason=[disconnected] message=[{message}]")

    async def close(self):
        self.closed = True

        if not self.websocket:
            return False

        await self.websocket.close()
        return True


async def send_presence_changed_event(server_name: str, sensor_id: SensorId, presence: bool):
    client = get_client(server_name)
    if not client:
        if server_name not in _missing_servers:
            _missing_servers.add(server_name)
            logger.warning(f"[websocket_server_missing] name=[{server_name}]")
        return

    _missing_servers.discard(server_name)

    payload = {
        "sensorId": f"{sensor_id.sensor_type.value}/{sensor_id.sensor_name}",
        "event": "presence_change",
        "eventAt": datetime.now(timezone.utc).isoformat(),
        "eventData": {"presence": presence},
    }
    await client.send_message(json.dumps(payload))
    logger.debug(f"[websocket_message_sent] server=[{server_name}] message=[{payload}]")


async def register(**config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config or not config[required_field]:
            raise MissingConfigurationField(required_field)

    name = config['name']
    uri = config['uri']

    if _clients.get(name):
        raise AlreadyRegistered

    client = WSClient(name, uri)
    server_task = asyncio.create_task(client.handle_connection())
    _clients[name] = (client, server_task)
    # Wait for the connection to prevent lost messages during init
    wait_sec = 1
    if not await client.wait_connected(wait_sec):
        logger.warning(f"[websocket_not_connected_during_init] wait_time=[{wait_sec}] server=[{name}] uri=[{uri}]")


async def unregister_all():
    for name, (client, task) in list(_clients.items()):
        if not client.closed:
            logger.info(f"[websocket_closing_connection] server=[{name}]")
            if not await client.close():
                task.cancel()
                await task
        del _clients[name]
