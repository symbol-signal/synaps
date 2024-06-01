import rich_click as click

from sensord.cli.sen0395 import start, stop, reset, latency, detrange, status, enable, disable


@click.group()
def cli():
    """
    Command-line tool for controlling sensord service.
    """
    pass


@cli.group()
def sen0395():
    """
    Subcommands for controlling the DFRobot mmWave presence sensor SEN0395.
    """
    pass


sen0395.add_command(start)
sen0395.add_command(stop)
sen0395.add_command(reset)
sen0395.add_command(latency)
sen0395.add_command(detrange)
sen0395.add_command(status)
sen0395.add_command(enable)
sen0395.add_command(disable)

if __name__ == "__main__":
    cli()
