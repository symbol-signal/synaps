from abc import ABC

from synaps.service import InvalidConfiguration, ksm
from synaps.service.ksm import KINCONY_SERVER_MINI

_platforms = {}


class RpioPlatform(ABC):
    pass


def register(platform_config):
    platform_type = platform_config['type']
    if KINCONY_SERVER_MINI.lower() != platform_type.lower():
        raise InvalidConfiguration(f"Unknown RPIO platform `{platform_type}`, supported: {[KINCONY_SERVER_MINI]}")

    kincony_server_mini = ksm.create_platform(platform_config)
    _platforms[KINCONY_SERVER_MINI] = kincony_server_mini


def unregister_all():
    for name, platform in list(_platforms.items()):
        platform.close()
        del _platforms[name]
