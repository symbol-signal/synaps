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
from typing import List, Optional

from sensord.service.err import SensordException

API_SOCKET = 'sensord.sock'
CONFIG_DIR = 'sensord'
SENSORS_CONFIG_FILE = 'sensors.toml'
MQTT_CONFIG_FILE = 'mqtt.toml'
WS_CONFIG_FILE = 'ws.toml'


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


def lookup_ws_config_file():
    return lookup_file_in_config_path(WS_CONFIG_FILE)


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
            if os.path.exists(home):
                path = home / '.cache'
            else:
                # Fallback for system no-login user
                path = Path('/var/log')
                create = False

    if create:
        os.makedirs(path / 'sensord', exist_ok=True)

    return path / 'sensord' / 'sensord.log'


def socket_dir() -> Path:
    """
    1. Root user: /run
    2. Non-root user: /tmp (An alternative may be: ${HOME}/.cache/sensord)
    :return: directory path for unix domain sockets
    """

    if _is_root():
        path = Path('/run')
    else:
        path = Path(f"/tmp")

    return path


def socket_path(socket_name: str) -> Path:
    """
    1. Root user: /run/{socket-name}
    2. Non-root user: /tmp/{socket-name} (An alternative may be: ${HOME}/.cache/sensord/{socket-name})

    :param socket_name: socket file name
    :return: unix domain socket path
    """

    return socket_dir() / socket_name


def api_socket_path():
    return socket_path(API_SOCKET)


def search_api_socket() -> Optional[Path]:
    """
    Search for the API socket file in the following directories:
    1. Root user: /run/{socket-name}
    2. Non-root user: /tmp/{socket-name}

    :return: socket file path if found, None otherwise
    """
    root_path = Path('/run') / API_SOCKET
    if root_path.exists():
        return root_path

    non_root_path = Path('/tmp') / API_SOCKET
    if non_root_path.exists():
        return non_root_path

    return None


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
