import os
import secrets
from datetime import datetime

TRUE_OPTIONS = ('yes', 'true', 'y', '1', 'on')


def str_to_bool(value: str):
    return value.lower() in TRUE_OPTIONS


def unique_timestamp_hex(random_suffix_length=4):
    return secrets.token_hex(random_suffix_length) + format(int(datetime.utcnow().timestamp() * 1000000), 'x')[::-1]


def expand_user(file):
    if not isinstance(file, str) or not file.startswith('~'):
        return file

    return os.path.expanduser(file)
