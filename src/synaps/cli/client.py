import json
from functools import wraps
from typing import List, Dict

from rich.console import Console

from synaps.common import sen0311, paths
from synaps.common.sen0395 import SensorStatuses, SensorCommandResponse, SensorConfigChainResponse, SensorConfigs
from synaps.common.socket import SocketClient, ServerResponse


class APIClient(SocketClient):

    def __init__(self, socket_path):
        super().__init__(lambda: [socket_path], bidirectional=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def send_request(self, method: str, params=None, request_id=None) -> Dict:
        if not params:
            params = {}

        req_body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }

        server_responses: List[ServerResponse] = self.communicate(json.dumps(req_body))
        if len(server_responses) > 1:
            raise MultiResponseException

        if not server_responses:
            raise NoService

        service_response = server_responses[0]

        if service_response.error:
            raise ServiceErrorException(service_response.error)

        service_response = json.loads(service_response.response)
        if "error" in service_response:
            raise ServiceFailureException(service_response["error"])

        return service_response

    def send_command_sen0395(self, command, args=(), sensor_name=None) -> List[SensorCommandResponse]:
        params = {'name': sensor_name, 'command': command.value, 'args': args}
        service_response = self.send_request('sen0395.command', params)

        responses = []
        for cmd_resp in service_response["result"]["sensor_command_responses"]:
            responses.append(SensorCommandResponse.deserialize(cmd_resp))

        return responses

    def send_configure_sen0395(self, command, args=(), sensor_name=None) -> List[SensorConfigChainResponse]:
        params = {'name': sensor_name, 'command': command.value, 'args': args}
        service_response = self.send_request('sen0395.configure', params)

        responses = []
        for config_resp in service_response["result"]["sensor_config_chain_responses"]:
            responses.append(SensorConfigChainResponse.deserialize(config_resp))

        return responses

    def send_get_status_sen0395(self, sensor_name=None) -> SensorStatuses:
        params = {'name': sensor_name}
        service_response = self.send_request('sen0395.status', params)
        return SensorStatuses.deserialize(service_response["result"])

    def send_get_config_sen0395(self, sensor_name=None) -> SensorConfigs:
        params = {'name': sensor_name}
        service_response = self.send_request('sen0395.config', params)
        return SensorConfigs.deserialize(service_response["result"])

    def send_reading_enabled_sen0395(self, enabled, sensor_name=None) -> SensorStatuses:
        params = {'name': sensor_name, 'enabled': enabled}
        service_response = self.send_request('sen0395.reading', params)
        return SensorStatuses.deserialize(service_response["result"])

    def send_get_status_sen0311(self, sensor_name=None) -> sen0311.SensorStatuses:
        params = {'name': sensor_name}
        service_response = self.send_request('sen0311.status', params)
        return sen0311.SensorStatuses.deserialize(service_response["result"])

def service_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        console = Console()
        api_socket_path = paths.search_api_socket()
        if not api_socket_path:
            console.print("[bold red]Synapsd service is not running:[/bold red] Start the service by `synapsd` command")
            raise SystemExit(1)

        with APIClient(api_socket_path) as client:
            try:
                return func(client, console, *args, **kwargs)
            except PermissionError as e:
                console.print(f"[bold red]Access Denied: [/bold red]{e}")
            except ServiceException as e:
                console.print(f"[bold red]Service Error: [/bold red]{e}")

    return wrapper


class ServiceException(Exception):
    pass


class NoService(ServiceException):

    def __init__(self):
        super().__init__('The service is not running')


class MultiResponseException(ServiceException):

    def __init__(self):
        super().__init__('Unexpected condition: Multiple services are running')


class ServiceFailureException(ServiceException):

    def __init__(self, error):
        self.error = error
        super().__init__(f"The service returned error response: {error}")


class ServiceErrorException(ServiceException):

    def __init__(self, error):
        self.error = error
        super().__init__(f"Error when communicating with the service: {error}")
