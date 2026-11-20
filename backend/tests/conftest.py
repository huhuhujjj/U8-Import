"""Isolate all pytest logs, including child processes, from Alloy's runtime path."""
import logging
import os
import tempfile


def pytest_configure(config):
    config._u8_log_temp = tempfile.TemporaryDirectory(prefix='u8-pytest-logs-')
    config._u8_log_previous = {key: os.environ.get(key) for key in ('LOG_DIR', 'U8_LOG_ENV')}
    os.environ['LOG_DIR'] = config._u8_log_temp.name
    os.environ['U8_LOG_ENV'] = 'test'


def pytest_unconfigure(config):
    if not hasattr(config, '_u8_log_temp'):
        return
    for handler in list(logging.getLogger().handlers):
        if getattr(handler, 'u8_handler', False):
            logging.getLogger().removeHandler(handler)
            handler.close()
    for key, value in config._u8_log_previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    config._u8_log_temp.cleanup()
