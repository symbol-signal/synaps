import json
from typing import List, Dict

from sensation.sen0395 import CommandResponse
from sensord.common.sen0395 import SensorStatuses, SensorCommandResponse, SensorConfigChainResponse
from sensord.common.socket import SocketClient, ServerResponse
from sensord.service import paths
from sensord.service.api import API_FILE_EXTENSION


class APIClient(SocketClient):

    def __init__(self):
        super().__init__(paths.socket_files_provider(API_FILE_EXTENSION), bidirectional=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def send_request(self, api: str, req_body=None) -> Dict:
        if not req_body:
            req_body = {}
        req_body["request_metadata"] = {"api": api}

        server_responses: List[ServerResponse] = self.communicate(json.dumps(req_body))
        if len(server_responses) > 1:
            raise MultiResponseException

        if not server_responses:
            raise NoService

        service_response = server_responses[0]

        if service_response.error:
            raise ServiceErrorException(service_response.error)

        service_response = json.loads(service_response.response)
        if error := service_response["response_metadata"].get("error"):
            raise ServiceFailureException(error)

        return service_response

    def send_command_sen0395(self, command, params=(), sensor_name=None) -> List[SensorCommandResponse]:
        service_response = self.send_request(
            '/sen0395/command', {'name': sensor_name, 'command': command.value, 'parameters': params})

        responses = []
        for cmd_resp in service_response["response"]["sensor_command_responses"]:
            responses.append(SensorCommandResponse.deserialize(cmd_resp))

        return responses

    def send_configure_sen0395(self, command, params=(), sensor_name=None) -> List[SensorConfigChainResponse]:
        service_response = self.send_request(
            '/sen0395/configure', {'name': sensor_name, 'command': command.value, 'parameters': params})

        responses = []
        for config_resp in service_response["response"]["sensor_config_chain_responses"]:
            responses.append(SensorConfigChainResponse.deserialize(config_resp))

        return responses

    def send_get_status_sen0395(self, sensor_name=None) -> List[CommandResponse]:
        service_response = self.send_request('/sen0395/status', {'name': sensor_name})
        return SensorStatuses.deserialize(service_response["response"])


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
