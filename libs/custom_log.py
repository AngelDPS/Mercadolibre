import logging
import logging.handlers
import sys
import os

LOG_DIRECTORY = "logs"
LOG_FILE = "MeLi.log"
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)


def getLogger(name: str = None) -> logging.Logger:
    # create logger with 'name'
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(LOG_DIRECTORY, LOG_FILE),
        when='midnight',
        interval=1,
        backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)
    # create formatter and add it to the handlers
    precise_formatter = logging.Formatter(
        '%(asctime)s;%(name)-15s;%(levelname)-8s;%(message)s')
    brief_formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(precise_formatter)
    console_handler.setFormatter(brief_formatter)
    # add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
