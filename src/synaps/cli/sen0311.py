import rich_click as click
from rich.console import Console

from synaps.cli.client import service_call, APIClient


@click.group()
def sen0311():
    """
    Subcommand group for controlling the DFRobot ultrasonic distance sensor SEN0311.
    """
    pass

@sen0311.command()
@click.option('--name', help='The name of the specific sensor to get the status.')
@service_call
def status(client: APIClient, console: Console, name):
    """Print current sensor status"""
    statuses = client.send_get_status_sen0311(sensor_name=name)
    console.print(statuses)
