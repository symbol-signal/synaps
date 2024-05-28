# sen0395_commands.py
from functools import wraps

import rich_click as click
from rich.console import Console

from sensation.sen0395 import range_segments, Command
from sensord.cli.client import APIClient, ServiceException
from sensord.common.sen0395 import sensor_command_responses_table
from sensord.service import paths


@click.group()
def sen0395():
    """
    Subcommand group for controlling the DFRobot mmWave presence sensor SEN0395.
    """
    pass


@sen0395.command()
def start():
    send_command(Command.SENSOR_START)


@sen0395.command()
def stop():
    send_command(Command.SENSOR_STOP)


@sen0395.command()
def reset():
    send_command(Command.RESET_SYSTEM)


@sen0395.command()
@click.argument('detection_delay', type=click.IntRange(0, 65535))
@click.argument('disappearance_delay', type=click.IntRange(0, 65535))
def latency(detection_delay, disappearance_delay):
    delay_detection_ms = detection_delay * 25
    delay_disappearance_ms = disappearance_delay * 25
    console = Console()
    console.print(f"Delay on detection: {delay_detection_ms} ms, "
                  f"Delay after disappearance: {delay_disappearance_ms} ms")

    send_command(Command.LATENCY_CONFIG, [-1, detection_delay, disappearance_delay])


@sen0395.command()
@click.argument('para_s', type=int)
@click.argument('para_e', type=int)
@click.argument('parb_s', type=int, required=False, default=None)
@click.argument('parb_e', type=int, required=False, default=None)
@click.argument('parc_s', type=int, required=False, default=None)
@click.argument('parc_e', type=int, required=False, default=None)
@click.argument('pard_s', type=int, required=False, default=None)
@click.argument('pard_e', type=int, required=False, default=None)
def detrange(para_s, para_e, parb_s, parb_e, parc_s, parc_e, pard_s, pard_e):
    params = [p for p in (para_s, para_e, parb_s, parb_e, parc_s, parc_e, pard_s, pard_e) if p is not None]

    try:
        segments = range_segments(params)
        console = Console()
        console.print("Sensing distance: " + " ".join(f'<{begin * 15}cm to {end * 15}cm>' for begin, end in segments))
    except ValueError as e:
        raise click.BadParameter(str(e))

    send_command(Command.DETECTION_RANGE_CONFIG, [-1] + params)

def service_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        console = Console()
        api_socket_path = paths.search_api_socket()
        if not api_socket_path:
            console.print("[bold red]Sensord service is not running:[/bold red] Start the service by `sensord` command")
            raise SystemExit(1)

        with APIClient(api_socket_path) as client:
            try:
                return func(client, console, *args, **kwargs)
            except ServiceException as e:
                console.print(f"[bold red]Service Error: [/bold red]{e}")
    return wrapper

@sen0395.command()
@service_call
def status(client: APIClient, console: Console):
    statuses = client.send_get_status_sen0395()
    console.print(statuses)


@sen0395.command()
@service_call
def enable(client: APIClient, console: Console):
    statuses = client.send_reading_enabled_sen0395(True)
    console.print(statuses)

@sen0395.command()
@service_call
def disable(client: APIClient, console: Console):
    statuses = client.send_reading_enabled_sen0395(False)
    console.print(statuses)


@service_call
def send_command(client: APIClient, console: Console, cmd, params=None, sensor_name=None):
    if cmd.is_config:
        responses = client.send_configure_sen0395(cmd, params, sensor_name)
        for cfg_chain_resp in responses:
            console.print(cfg_chain_resp)
    else:
        responses = client.send_command_sen0395(cmd, params, sensor_name)
        console.print(sensor_command_responses_table(*responses))
