from dataclasses import dataclass
from typing import List, Dict

from rich.box import MINIMAL
from rich.table import Table
from rich.text import Text

from sensation.sen0311 import SensorStatus


@dataclass
class SensorStatuses:
    statuses: List[SensorStatus]

    @classmethod
    def deserialize(cls, data: Dict) -> 'SensorStatuses':
        statuses = [SensorStatus.deserialize(status) for status in data['statuses']]
        return cls(statuses=statuses)

    def serialize(self):
        return {"statuses": [status.serialize() for status in self.statuses]}

    def __rich__(self):
        table = Table(show_header=True, box=MINIMAL)
        table.add_column("Name")
        table.add_column("Port")
        table.add_column("Enabled")
        table.add_column("Measurement")

        for status in self.statuses:
            reading = Text("Yes", style="green") if status.is_reading else Text("No", style="orange3")
            table.add_row(
                f"[bold blue]{status.sensor_id.sensor_name}[/bold blue]",
                status.port,
                reading,
                str(status.measurement),
            )

        return table
