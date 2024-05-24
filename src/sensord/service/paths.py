"""
Followed conventions:
 - https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
 - https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s15.html

Discussion:
 - https://askubuntu.com/questions/14535/whats-the-local-folder-for-in-my-home-directory

 TODO Read XDG env variables: https://wiki.archlinux.org/index.php/XDG_Base_Directory
"""

import getpass
import os
import re
from pathlib import Path
from typing import Generator, List, Callable

from sensord.service.err import SensordException

CONFIG_DIR = 'sensord'
SENSORS_CONFIG_FILE = 'sensors.toml'
MQTT_CONFIG_FILE = 'mqtt.toml'


class ConfigFileNotFoundError(SensordException, FileNotFoundError):

    def __init__(self, file, search_path=()):
        self.file = file
        self.search_path = search_path

        if search_path:
            message = f"Config file `{file}` not found in the search path: {', '.join([str(dir_) for dir_ in search_path])}"
        else:
            message = f"Config file `{file}` not found"

        super().__init__(message)


def _is_root():
    return os.geteuid() == 0


def lookup_sensors_config_file():
    return lookup_file_in_config_path(SENSORS_CONFIG_FILE)


def lookup_mqtt_config_file():
    return lookup_file_in_config_path(MQTT_CONFIG_FILE)


def lookup_file_in_config_path(file) -> Path:
    """Returns config found in the search path
    :return: config file path
    :raise FileNotFoundError: when config lookup failed
    """
    search_path = runtools_config_file_search_path()
    for config_dir in search_path:
        config = config_dir / file
        if config.exists():
            return config

    raise ConfigFileNotFoundError(file, search_path)


def runtools_config_file_search_path(*, exclude_cwd=False) -> List[Path]:
    search_path = config_file_search_path(exclude_cwd=exclude_cwd)

    if exclude_cwd:
        return [path / CONFIG_DIR for path in search_path]
    else:
        return [search_path[0]] + [path / CONFIG_DIR for path in search_path[1:]]


def config_file_search_path(*, exclude_cwd=False) -> List[Path]:
    """Sorted list of directories in which the program should look for configuration files:

    1. Current working directory unless `exclude_cwd` is True
    2. ${XDG_CONFIG_HOME} or defaults to ${HOME}/.config
    3. ${XDG_CONFIG_DIRS} or defaults to /etc/xdg
    4. /etc

    Related discussion: https://stackoverflow.com/questions/1024114
    :return: list of directories for configuration file lookup
    """
    search_path = []
    if not exclude_cwd:
        search_path.append(Path.cwd())

    search_path.append(xdg_config_home())
    search_path += xdg_config_dirs()
    search_path.append(Path('/etc'))

    return search_path


def xdg_config_home() -> Path:
    if os.environ.get('XDG_CONFIG_HOME'):
        return Path(os.environ['XDG_CONFIG_HOME'])
    else:
        return Path.home() / '.config'


def xdg_config_dirs() -> List[Path]:
    if os.environ.get('XDG_CONFIG_DIRS'):
        return [Path(path) for path in re.split(r":", os.environ['XDG_CONFIG_DIRS'])]
    else:
        return [Path('/etc/xdg')]


def log_file_path(create: bool) -> Path:
    """
    1. Root user: /var/log/sensord/{log-file}
    2. Non-root user: ${XDG_CACHE_HOME}/sensord/{log-file} or default to ${HOME}/.cache/sensord

    :param create: create path directories if not exist
    :return: log file path
    """

    if _is_root():
        path = Path('/var/log')
    else:
        if os.environ.get('XDG_CACHE_HOME'):
            path = Path(os.environ['XDG_CACHE_HOME'])
        else:
            home = Path.home()
            path = home / '.cache'

    if create:
        os.makedirs(path / 'sensord', exist_ok=True)

    return path / 'sensord' / 'sensord.log'


def socket_dir(create: bool) -> Path:
    """
    1. Root user: /run/sensord
    2. Non-root user: /tmp/taro_${USER} (An alternative may be: ${HOME}/.cache/sensord)

    TODO taro_${USER} should be unique to prevent denial of service attempts:

    :param create: create path directories if not exist
    :return: directory path for unix domain sockets
    :raises FileNotFoundError: when path cannot be created (only if create == True)
    """

    if _is_root():
        path = Path('/run/sensord')
    else:
        path = Path(f"/tmp/sensord_{getpass.getuser()}")

    if create:
        path.mkdir(mode=0o700, exist_ok=True)

    return path


def socket_path(socket_name: str, create: bool) -> Path:
    """
    1. Root user: /run/sensord/{socket-name}
    2. Non-root user: /tmp/taro_${USER}/{socket-name} (An alternative may be: ${HOME}/.cache/sensord/{socket-name})

    :param socket_name: socket file name
    :param create: create path directories if not exist
    :return: unix domain socket path
    :raises FileNotFoundError: when path cannot be created (only if create == True)
    """

    return socket_dir(create) / socket_name


def socket_files(file_extension: str) -> Generator[Path, None, None]:
    s_dir = socket_dir(False)
    if s_dir.exists():
        for entry in s_dir.iterdir():
            if entry.is_socket() and file_extension == entry.suffix:
                yield entry


def socket_files_provider(file_extension: str) -> Callable[[], Generator[Path, None, None]]:
    def provider():
        return socket_files(file_extension)

    return provider


def lock_dir(create: bool) -> Path:
    """
    1. Root user: /run/lock/sensord
    2. Non-root user: /tmp/taro_${USER}

    :param create: create path directories if not exist
    :return: directory path for file locks
    :raises FileNotFoundError: when path cannot be created (only if create == True)
    """

    if _is_root():
        path = Path('/run/lock/sensord')
    else:
        path = Path(f"/tmp/sensord_{getpass.getuser()}")

    if create:
        path.mkdir(mode=0o700, exist_ok=True)

    return path


def lock_path(lock_name: str, create: bool) -> Path:
    """
    1. Root user: /run/lock/sensord/{lock-name}
    2. Non-root user: /tmp/taro_${USER}/{lock-name}

    :param lock_name: socket file name
    :param create: create path directories if not exist
    :return: path of a file to be used as a lock
    :raises FileNotFoundError: when path cannot be created (only if create == True)
    """

    return lock_dir(create) / lock_name
