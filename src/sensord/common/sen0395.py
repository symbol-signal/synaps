from dataclasses import dataclass
from typing import List, Dict

from rich.box import MINIMAL
from rich.console import RenderableType, Group
from rich.table import Table
from rich.text import Text

from sensation.common import SensorId
from sensation.sen0395 import SensorStatus, CommandResponse, CommandResult, ConfigChainResponse

_CMD_RES_COLOURS = {
    CommandResult.DONE: "green",
    CommandResult.NOT_APPLICABLE: "green",
    CommandResult.ERROR: "red",
    CommandResult.MISSING: "red",
    CommandResult.UNKNOWN: "yellow",
}


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
        table.add_column("Enabled")
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
