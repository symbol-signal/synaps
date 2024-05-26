import logging
from logging import handlers

from rich.logging import RichHandler

from sensord.common import expand_user
from sensord.service import paths

sensord_logger = logging.getLogger('sensord')
sensord_logger.setLevel(logging.DEBUG)

STDOUT_FORMATTER = logging.Formatter('%(message)s')
DEF_FORMATTER = logging.Formatter('%(asctime)s - %(levelname)-5s - %(name)s - %(message)s')

STDOUT_HANDLER_NAME = 'stdout-handler'
FILE_HANDLER_NAME = 'file-handler'


def configure(enabled, log_file_level='info', log_file_path=None):
    if not enabled:
        sensord_logger.disabled = True
        return

    setup_console('DEBUG')

    if log_file_level != 'off':
        level = logging.getLevelName(log_file_level.upper())
        log_file_path = expand_user(log_file_path) or paths.log_file_path(create=True)
        setup_file(level, log_file_path)
        if level < sensord_logger.getEffectiveLevel():
            sensord_logger.setLevel(level)


def is_disabled():
    return sensord_logger.disabled


def setup_console(level):
    stdout_handler = RichHandler(show_path=False, log_time_format="[%X]")
    stdout_handler.set_name(STDOUT_HANDLER_NAME)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(STDOUT_FORMATTER)
    # stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)
    register_handler(stdout_handler)


def setup_file(level, file):
    file_handler = logging.handlers.WatchedFileHandler(file)
    file_handler.set_name(FILE_HANDLER_NAME)
    file_handler.setLevel(level)
    file_handler.setFormatter(DEF_FORMATTER)
    register_handler(file_handler)


def _find_handler(name):
    for handler in sensord_logger.handlers:
        if handler.name == name:
            return handler

    return None


def register_handler(handler):
    previous = _find_handler(handler.name)
    if previous:
        sensord_logger.removeHandler(previous)

    sensord_logger.addHandler(handler)
