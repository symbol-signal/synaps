import click

from sensord import service
from sensord.service import log


@click.command()
def main():
    log.configure(True)
    service.run()

if __name__ == "__main__":
    main()
