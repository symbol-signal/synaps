import logging
from logging import handlers

from rich.logging import RichHandler

from synaps.common import expand_user, paths

synapsd_logger = logging.getLogger('synaps')
synapsd_logger.setLevel(logging.DEBUG)

sensation_logger = logging.getLogger('sensation')
sensation_logger.setLevel(logging.DEBUG)

STDOUT_FORMATTER = logging.Formatter('%(message)s')
DEF_FORMATTER = logging.Formatter('%(asctime)s - %(levelname)-5s - %(name)s - %(message)s')

STDOUT_HANDLER_NAME = 'stdout-handler'
FILE_HANDLER_NAME = 'file-handler'


def configure(enabled, log_file_level='info', log_file_path=None):
    if not enabled:
        synapsd_logger.disabled = True
        sensation_logger.disabled = True
        return

    setup_console('DEBUG')

    if log_file_level != 'off':
        level = logging.getLevelName(log_file_level.upper())
        log_file_path = expand_user(log_file_path) or paths.log_file_path(create=True)
        setup_file(level, log_file_path)
        if level < synapsd_logger.getEffectiveLevel():
            synapsd_logger.setLevel(level)
            sensation_logger.setLevel(level)


def is_disabled():
    return synapsd_logger.disabled


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


def register_handler(handler):
    register_handler_for_logger(synapsd_logger, handler)
    register_handler_for_logger(sensation_logger, handler)


def _find_handler(logger, name):
    for handler in logger.handlers:
        if handler.name == name:
            return handler

    return None

def register_handler_for_logger(logger, handler):
    previous = _find_handler(logger, handler.name)
    if previous:
        logger.removeHandler(previous)

    logger.addHandler(handler)
