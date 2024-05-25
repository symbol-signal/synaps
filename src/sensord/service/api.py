import json
import logging
from abc import ABC, abstractmethod
from json import JSONDecodeError

import sensord.service.sen0395
from sensation.sen0395 import Command
from sensord import common
from sensord.common.sen0395 import SensorStatuses, SensorConfigChainResponse, SensorCommandResponse
from sensord.common.socket import SocketServer, SocketServerStoppedAlready
from sensord.service import paths

log = logging.getLogger(__name__)

API_FILE_EXTENSION = '.api'


def _create_socket_name():
    return common.unique_timestamp_hex() + API_FILE_EXTENSION


class _ApiError(Exception):

    def __init__(self, code, error):
        self.code = code
        self.error = error

    def create_response(self):
        return _resp_err(self.code, self.error)


def _missing_field_error(field) -> _ApiError:
    return _ApiError(422, f"Missing field {field}")


def _no_sensor_error(sensor) -> _ApiError:
    return _ApiError(404, f"Sensor {sensor} not found")


def _no_sensors_error() -> _ApiError:
    return _ApiError(404, f"No sensors found")


def _unknown_command_error(cmd) -> _ApiError:
    return _ApiError(422, f"Command {cmd} is not recognized")


def _resp_ok(response):
    return _resp(200, response)


def _resp(code: int, response):
    resp = {
        "response_metadata": {"code": code},
        "response": response
    }
    return json.dumps(resp)


def _resp_err(code: int, reason: str):
    if 400 > code >= 600:
        raise ValueError("Error code must be 4xx or 5xx")

    err_resp = {
        "response_metadata": {"code": code, "error": {"reason": reason}}
    }

    return json.dumps(err_resp)


class APIResource(ABC):

    @property
    @abstractmethod
    def path(self):
        """Path of the resource including leading '/' character"""

    @abstractmethod
    def handle(self, req_body):
        """Handle request and optionally return response or raise :class:`__ServerError"""

    def validate(self, req_body):
        """Raise :class:`__ServerError if request body is invalid"""


def _get_sensors(sensor_name):
    if sensor_name:
        sensor = sensord.service.sen0395.get_sensor(sensor_name)
        if not sensor:
            raise _no_sensor_error(sensor_name)

        return [sensor]

    sensors = sensord.service.sen0395.get_all_sensors()

    if not sensors:
        raise _no_sensors_error()

    return sensors


class APISen0395Command(APIResource):

    @property
    def path(self):
        return '/sen0395/command'

    def handle(self, req_body):
        sensors = _get_sensors(req_body.get('name'))

        cmd = Command.from_value(req_body['command'])

        if not cmd:
            raise _unknown_command_error(req_body['command'])

        params = req_body.get('parameters') or ()

        responses = []
        for sensor in sensors:
            cmd_resp = sensor.send_command(cmd, *params)
            responses.append(SensorCommandResponse(sensor.sensor_id, cmd_resp).serialize())

        return {"sensor_command_responses": responses}

    def validate(self, req_body):
        if 'command' not in req_body:
            raise _missing_field_error('command')


class APISen0395Configure(APIResource):

    @property
    def path(self):
        return '/sen0395/configure'

    def handle(self, req_body):
        sensors = _get_sensors(req_body.get('name'))

        cmd = Command.from_value(req_body['command'])

        if not cmd:
            raise _unknown_command_error(req_body['command'])

        if not cmd.is_config:
            raise _ApiError(422, f"Command {cmd} is not a configuration command")

        params = req_body.get('parameters') or ()

        responses = []
        for sensor in sensors:
            config_chain_resp = sensor.configure(cmd, *params)
            responses.append(SensorConfigChainResponse(sensor.sensor_id, config_chain_resp).serialize())

        return {"sensor_config_chain_responses": responses}

    def validate(self, req_body):
        if 'command' not in req_body:
            raise _missing_field_error('command')


class APISen0395Status(APIResource):

    @property
    def path(self):
        return '/sen0395/status'

    def handle(self, req_body):
        sensors = _get_sensors(req_body.get('name'))

        statuses = []
        for sensor in sensors:
            statuses.append(sensor.status())

        return SensorStatuses(statuses).serialize()


DEFAULT_RESOURCES = (APISen0395Command(), APISen0395Configure(), APISen0395Status())


class APIServer(SocketServer):

    def __init__(self, resources=DEFAULT_RESOURCES):
        super().__init__(lambda: paths.socket_path(_create_socket_name(), create=True), allow_ping=True)
        self._resources = {resource.path: resource for resource in resources}

    def handle(self, req):
        try:
            req_body = json.loads(req)
        except JSONDecodeError as e:
            log.warning(f"event=[invalid_json_request_body] length=[{e}]")
            return _resp_err(400, "invalid_req_body")

        if 'request_metadata' not in req_body:
            return _resp_err(422, "missing_field:request_metadata")

        try:
            resource = self._resolve_resource(req_body)
            resource.validate(req_body)
        except _ApiError as e:
            return e.create_response()

        try:
            return _resp_ok(resource.handle(req_body))
        except _ApiError as e:
            return e.create_response()
        except Exception:
            log.error("event=[api_handler_error]", exc_info=True)
            return _resp_err(500, 'Unexpected API handler error')

    def _resolve_resource(self, req_body) -> APIResource:
        if 'api' not in req_body['request_metadata']:
            raise _missing_field_error('request_metadata.api')

        api = req_body['request_metadata']['api']
        resource = self._resources.get(api)
        if not resource:
            raise _ApiError(404, f"{api} API not found")

        return resource


_api_server = APIServer()


def start():
    try:
        _api_server.start()
    except SocketServerStoppedAlready:
        pass  # Stopped before started -> ignore..


def stop():
    _api_server.close_and_wait()
