import abc
import asyncio
import logging
import os
import socket
import stat
from asyncio import DatagramProtocol
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from types import coroutine
from typing import List, NamedTuple, Optional

# Default=32768, Max= 262142, https://docstore.mik.ua/manuals/hp-ux/en/B2355-60130/UNIX.7P.html
RECV_BUFFER_LENGTH = 65536  # Can be increased to 163840?

log = logging.getLogger(__name__)


class SocketServerException(Exception):
    pass


class SocketBindException(SocketServerException):

    def __init__(self, socket_path):
        self.socket_path = socket_path
        super().__init__(f"Unable to create socket: {socket_path}")


class PayloadTooLarge(SocketServerException):
    """
    This exception is thrown when the operating system rejects sent datagram due to its size.
    """

    def __init__(self, payload_size):
        super().__init__("Datagram payload is too large: " + str(payload_size))


class SocketServerStoppedAlready(SocketServerException):
    pass


class SocketServerAsync(abc.ABC, DatagramProtocol):

    def __init__(self, socket_path: Path, *, allow_ping=False):
        self._socket_path = socket_path
        self._allow_ping = allow_ping
        self._transport = None

    async def start(self):
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.bind(str(self._socket_path))
            self._transport, _ = await loop.create_datagram_endpoint(lambda: self, sock=sock)
        except OSError as e:
            raise SocketBindException(self._socket_path) from e

        # Allow users from the same group to communicate with the server
        os.chmod(self._socket_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)
        log.info('[socket_server_started]')

    def datagram_received(self, data, addr):
        asyncio.create_task(self._handle_datagram(data, addr))

    async def _handle_datagram(self, data, addr):
        if not data:
            return

        req_body = data.decode()
        if self._allow_ping and req_body == 'ping':
            resp_body = 'pong'
        else:
            resp_body = await self.handle(req_body)

        if resp_body:
            try:
                self._transport.sendto(resp_body.encode(), addr)
            except OSError as e:
                if e.errno == 90:
                    log.error(f"[server_response_payload_too_large] length=[{len(resp_body.encode())}]")

    @abc.abstractmethod
    async def handle(self, req_body):
        """
        Handle request and optionally return response
        :return: response body or None if no response
        """

    async def stop(self):
        if not self._transport:
            return

        try:
            self._transport.close()
        finally:
            self._transport = None
            if os.path.exists(self._socket_path):
                os.remove(self._socket_path)

        log.info('[socket_server_stopped]')


class Error(Enum):
    TIMEOUT = auto()


class ServerResponse(NamedTuple):
    server_id: str
    response: Optional[str]
    error: Error = None


@dataclass
class PingResult:
    active_servers: List[str]
    timed_out_servers: List[str]
    stale_sockets: List[Path]


class SocketClient:

    def __init__(self, servers_provider, bidirectional: bool, *, timeout=10):
        self._servers_provider = servers_provider
        self._bidirectional = bidirectional
        self._client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        if bidirectional:
            self._client.bind(self._client.getsockname())
            self._client.settimeout(timeout)
        self.timed_out_servers = []
        self.stale_sockets = []

    @coroutine
    def servers(self, include=()):
        """

        :param include: server IDs exact match filter
        :return: response if bidirectional
        :raises PayloadTooLarge: when request payload is too large
        """
        req_body = '_'  # Dummy initialization to remove warnings
        resp = None
        skip = False
        for server_file in self._servers_provider():
            server_id = server_file.stem
            if (server_file in self.stale_sockets) or (include and server_id not in include):
                continue
            while True:
                if not skip:
                    req_body = yield resp
                skip = False  # reset
                if not req_body:
                    break  # next(this) called -> proceed to the next server

                encoded = req_body.encode()
                try:
                    self._client.sendto(encoded, str(server_file))
                    if self._bidirectional:
                        datagram = self._client.recv(RECV_BUFFER_LENGTH)
                        resp = ServerResponse(server_id, datagram.decode())
                except TimeoutError:
                    log.warning('[socket_timeout] socket=[{}]'.format(server_file))
                    self.timed_out_servers.append(server_id)
                    resp = ServerResponse(server_id, None, Error.TIMEOUT)
                except ConnectionRefusedError:  # TODO what about other errors?
                    log.warning('[stale_socket] socket=[{}]'.format(server_file))
                    self.stale_sockets.append(server_file)
                    skip = True  # Ignore this one and continue with another one
                    break
                except OSError as e:
                    if e.errno == 2 or e.errno == 32:
                        continue  # The server closed meanwhile
                    if e.errno == 90:
                        raise PayloadTooLarge(len(encoded))
                    raise e

    def communicate(self, req, include=()) -> List[ServerResponse]:
        server = self.servers(include=include)
        responses = []
        while True:
            try:
                next(server)
                responses.append(server.send(req))  # StopIteration is raised from this function if last socket is dead
            except StopIteration:
                break
        return responses

    def ping(self) -> PingResult:
        responses = self.communicate('ping')
        active = [resp.server_id for resp in responses if resp]
        timed_out = list(self.timed_out_servers)
        stale = list(self.stale_sockets)
        return PingResult(active, timed_out, stale)

    def close(self):
        self._client.shutdown(socket.SHUT_RDWR)
        self._client.close()
