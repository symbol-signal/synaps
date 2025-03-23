# sen0395_commands.py

import rich_click as click
from rich.console import Console

from sensation.sen0395 import range_segments, Command
from synaps.cli.client import APIClient, service_call
from synaps.common.sen0395 import sensor_command_responses_table


@click.group()
def sen0395():
    """
    Subcommand group for controlling the DFRobot mmWave presence sensor SEN0395.
    """
    pass


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to start scanning.')
def start(name):
    """Start scanning"""
    send_command(Command.SENSOR_START, sensor_name=name)


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to stop scanning.')
def stop(name):
    """Stop scanning"""
    send_command(Command.SENSOR_STOP, sensor_name=name)


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to reset.')
def reset(name):
    """Send soft reset command"""
    send_command(Command.RESET_SYSTEM, sensor_name=name)


@sen0395.command()
@click.argument('detection_delay', type=click.IntRange(0, 65535))
@click.argument('disappearance_delay', type=click.IntRange(0, 65535))
@click.option('--name', help='The name of the specific sensor to configure latency.')
def latency(detection_delay, disappearance_delay, name):
    """Configure detection and disappearance latencies in 25ms unit"""
    delay_detection_ms = detection_delay * 25
    delay_disappearance_ms = disappearance_delay * 25
    console = Console()
    console.print(f"Delay on detection: {delay_detection_ms} ms, "
                  f"Delay after disappearance: {delay_disappearance_ms} ms")

    send_command(Command.LATENCY_CONFIG, [-1, detection_delay, disappearance_delay], sensor_name=name)


@sen0395.command()
@click.argument('para_s', type=int)
@click.argument('para_e', type=int)
@click.argument('parb_s', type=int, required=False, default=None)
@click.argument('parb_e', type=int, required=False, default=None)
@click.argument('parc_s', type=int, required=False, default=None)
@click.argument('parc_e', type=int, required=False, default=None)
@click.argument('pard_s', type=int, required=False, default=None)
@click.argument('pard_e', type=int, required=False, default=None)
@click.option('--name', help='The name of the specific sensor to configure detection range.')
def detrange(para_s, para_e, parb_s, parb_e, parc_s, parc_e, pard_s, pard_e, name):
    """Configure detection ranges in 15cm unit"""
    params = [p for p in (para_s, para_e, parb_s, parb_e, parc_s, parc_e, pard_s, pard_e) if p is not None]

    try:
        segments = range_segments(params)
        console = Console()
        console.print("Sensing distance: " + " ".join(f'<{begin * 15}cm to {end * 15}cm>' for begin, end in segments))
    except ValueError as e:
        raise click.BadParameter(str(e))

    send_command(Command.DETECTION_RANGE_CONFIG, [-1] + params, sensor_name=name)


@sen0395.command()
@click.argument('value', type=click.IntRange(0, 9))
@click.option('--name', help='The name of the specific sensor to configure sensitivity.')
def sensitivity(value, name):
    """Configure sensor sensitivity value (0-9)"""
    send_command(Command.SET_SENSITIVITY, [value], sensor_name=name)


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to get the status.')
@service_call
def status(client: APIClient, console: Console, name):
    """Print current sensor status"""
    statuses = client.send_get_status_sen0395(sensor_name=name)
    console.print(statuses)


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to get the status.')
@service_call
def config(client: APIClient, console: Console, name):
    """Print stored sensor configuration"""
    configs = client.send_get_config_sen0395(sensor_name=name)
    console.print(configs)


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to enable reading and processing.')
@service_call
def enable(client: APIClient, console: Console, name):
    """Start reading and processing data"""
    statuses = client.send_reading_enabled_sen0395(True, sensor_name=name)
    console.print(statuses)


@sen0395.command()
@click.option('--name', help='The name of the specific sensor to disable reading and processing.')
@service_call
def disable(client: APIClient, console: Console, name):
    """Stop reading and processing data"""
    statuses = client.send_reading_enabled_sen0395(False, sensor_name=name)
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
