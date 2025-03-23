import rich_click as click

from synaps import __version__
from synaps.cli.sen0311 import sen0311
from synaps.cli.sen0395 import sen0395


@click.group()
@click.version_option(__version__)
def cli():
    """
    Command-line tool for controlling synaps service.
    """
    pass


cli.add_command(sen0311)
cli.add_command(sen0395)

if __name__ == "__main__":
    cli()
