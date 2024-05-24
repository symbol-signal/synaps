# sen0395_commands.py

import rich_click as click
from rich.console import Console

from sensation.sen0395 import range_segments, Command
from sensord.cli.client import APIClient, ServiceException
from sensord.common.sen0395 import sensor_command_responses_table


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


@sen0395.command()
def status():
    console = Console()
    with APIClient() as c:
        try:
            statuses = c.send_get_status_sen0395()
            console.print(statuses)
        except ServiceException as e:
            console.print(f"[bold red]Service Error: [/bold red]{e}")


def send_command(cmd, params=None, sensor_name=None):
    console = Console()
    with APIClient() as c:
        try:
            if cmd.is_config:
                responses = c.send_configure_sen0395(cmd, params, sensor_name)
                for cfg_chain_resp in responses:
                    console.print(cfg_chain_resp)
            else:
                responses = c.send_command_sen0395(cmd, params, sensor_name)
                console.print(sensor_command_responses_table(*responses))
        except ServiceException as e:
            console.print(f"[bold red]Service Error: [/bold red]{e}")
