import logging
from dataclasses import dataclass
from typing import List, Optional, Dict

from rich.box import MINIMAL
from rich.console import RenderableType, Group
from rich.table import Table
from rich.text import Text
from serial import Serial

from sensation.common import SensorId
from sensation.sen0395 import Sensor, PresenceHandler, SensorStatus, CommandResponse, CommandResult, ConfigChainResponse
from sensord.service import mqtt
from sensord.service.err import AlreadyRegistered, MissingConfigurationField, InvalidConfiguration

log = logging.getLogger(__name__)

_sensors = {}

REQUIRED_FIELDS = ['port']

_CMD_RES_COLOURS = {
    CommandResult.DONE: "green",
    CommandResult.NOT_APPLICABLE: "green",
    CommandResult.ERROR: "red",
    CommandResult.MISSING: "red",
    CommandResult.UNKNOWN: "yellow",
}


def register(**config):
    validate_config(config)

    if _sensors.get(config['name']):
        raise AlreadyRegistered

    sensor = _init_sensor(config)
    _sensors[config['name']] = sensor


def validate_config(config):
    for required_field in REQUIRED_FIELDS:
        if required_field not in config:
            raise MissingConfigurationField(required_field)
    if mqtt_brokers := config.get('mqtt'):
        if not isinstance(mqtt_brokers, list):
            raise InvalidConfiguration("`mqtt` field must be a list")

        for broker_config in mqtt_brokers:
            if 'broker' not in broker_config:
                raise MissingConfigurationField('mqtt.broker')
            if 'topic' not in broker_config:
                raise MissingConfigurationField('mqtt.topic')


def unregister_all():
    for name, sensor in list(_sensors.items()):
        sensor.close()
        del _sensors[name]


def get_all_sensors() -> List[Sensor]:
    return list(_sensors.values())


def get_sensor(name) -> Optional[Sensor]:
    return _sensors.get(name)


def _init_sensor(config):
    s = Sensor(config['name'], Serial(config['port'], 115200, timeout=1))
    handler = PresenceHandler()
    s.handlers.append(handler)

    if config.get('print_presence'):
        handler.observers.append(
            lambda presence: log.info(f"[presence_change] sensor=[{s.sensor_id}] presence=[{presence}]"))

    if mqtt_brokers := config.get("mqtt"):
        for conf in mqtt_brokers:
            handler.observers.append(
                lambda presence: mqtt.send_presence_changed_event(conf['broker'], conf['topic'], s.sensor_id, presence))

    if config.get('read_on_start'):
        s.start_reading()

    if config.get('autostart'):
        scanning = s.read_presence() is not None
        if scanning:
            log.info(f"[autostart] sensor=[{s.sensor_id}] result=[already_scanning]")
        else:
            resp = s.start_scanning()
            if resp:
                log.info(f"[autostart] sensor=[{s.sensor_id}] result=[started]")
            else:
                log.warning(f"[autostart] sensor=[{s.sensor_id}] result=[failed] response=[{resp}]")

    return s


@dataclass
class SensorStatuses:
    statuses: List[SensorStatus]

    @classmethod
    def deserialize(cls, data: Dict):
        statuses = [SensorStatus.deserialize(status) for status in data['statuses']]
        return cls(statuses=statuses)

    def serialize(self):
        return {"statuses": [status.serialize() for status in self.statuses]}

    def __rich__(self):
        table = Table(show_header=True, box=MINIMAL)
        table.add_column("Name")
        table.add_column("Port")
        table.add_column("Timeout")
        table.add_column("Reading")
        table.add_column("Scanning")

        for status in self.statuses:
            reading = Text("Yes", style="green") if status.is_reading else Text("No", style="orange3")
            scanning = Text("Yes", style="green") if status.is_scanning else Text("No", style="orange3")
            table.add_row(
                f"[bold blue]{status.sensor_id.sensor_name}[/bold blue]",
                status.port,
                str(status.timeout) if status.timeout is not None else "None",
                reading,
                scanning)

        return table


def sensor_command_responses_table(*responses):
    table = Table(show_header=True, box=None)
    table.add_column("Sensor ID")
    table.add_column("Command")
    table.add_column("Result", style="bold")
    table.add_column("Message")

    for resp in responses:
        cmd_echo = resp.command_response.command_echo or "<Unconfirmed>"
        result = resp.command_response.command_result.value
        message = resp.command_response.message or ""
        result_color = _CMD_RES_COLOURS[resp.command_response.command_result]

        table.add_row(str(resp.sensor_id), cmd_echo, f"[{result_color}]{result}[/{result_color}]", message)

    return table


@dataclass
class SensorCommandResponse:
    sensor_id: SensorId
    command_response: CommandResponse

    def serialize(self) -> Dict:
        return {
            "sensor_id": self.sensor_id.serialize(),
            "command_response": self.command_response.serialize(),
        }

    @classmethod
    def deserialize(cls, data: Dict):
        sensor_id = SensorId.deserialize(data["sensor_id"])
        command_response = CommandResponse.deserialize(data["command_response"])
        return cls(sensor_id=sensor_id, command_response=command_response)

    def __rich__(self):
        return sensor_command_responses_table(self)

    def __str__(self):
        return f"Sensor ID: {self.sensor_id}, Command Response: {self.command_response}"


@dataclass
class SensorConfigChainResponse:
    sensor_id: SensorId
    config_chain_response: ConfigChainResponse

    def serialize(self) -> Dict:
        return {
            "sensor_id": self.sensor_id.serialize(),  # Serializes the sensor ID
            "config_chain_response": self.config_chain_response.serialize(),  # Serializes the config chain responses
        }

    @classmethod
    def deserialize(cls, data: Dict) -> 'SensorConfigChainResponse':
        sensor_id = SensorId.deserialize(data["sensor_id"])
        config_chain_responses = ConfigChainResponse.deserialize(data["config_chain_response"])
        return cls(sensor_id=sensor_id, config_chain_response=config_chain_responses)

    def commands_map(self):
        return {
            "[dim]Pause[/dim]": self.config_chain_response.pause_cmd,
            "Configure": self.config_chain_response.cfg_cmd,
            "Save": self.config_chain_response.save_cmd,
            "[dim]Resume[/dim]": self.config_chain_response.resume_cmd,
        }

    def __rich__(self) -> RenderableType:
        table = Table(show_header=True, box=None)
        table.add_column("Operation")
        table.add_column("Command")
        table.add_column("Result", style="bold")
        table.add_column("Message")

        commands = self.commands_map()

        for cmd_name, cmd_response in commands.items():
            if cmd_response:
                cmd_echo = cmd_response.command_echo or "<Unconfirmed>"
                result = cmd_response.command_result.value
                message = cmd_response.message or ""
                result_color = _CMD_RES_COLOURS[cmd_response.command_result]

                table.add_row(cmd_name, cmd_echo, f"[{result_color}]{result}[/{result_color}]", message)

        sensor_info = Text().append("Sensor ID: ", style='bold').append(str(self.sensor_id))
        return Group(sensor_info, table)

    def __str__(self) -> str:
        return f"Sensor ID: {self.sensor_id}, Config Chain Responses: {self.config_chain_response}"
