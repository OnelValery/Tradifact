import logging
import datetime


def start_log(c):
    # there is some not very clear code to control independently what logger can do, basically
    # - the trading loop operates at one log level, and uses a specific file plus the common file
    # - all other loggers at a different log level and use only the common file
    # the basic config will be for the common file
    lib_log_level = getattr(logging, c.args.log_lib)
    logging.basicConfig(
        filename="../logs/ibapi_" + str(c.args.client) + ".log",
        format='%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
        level=lib_log_level,
        datefmt='%Y-%m-%d %H:%M:%S')

    # define a new log file name, this uses the start time in the local timezone
    local_now = datetime.datetime.now(c.local_tz)
    c.log_file = "../logs/" + c.args.name + "_" + local_now.strftime("%Y%m%d_%H%M%S") + ".log"

    # the log messages are split into three levels
    # - debug, the most detailed, enabled when --debug is present, only useful for low level tracing, per loop
    # - info, general info, not directly associated with trades but not at each loop
    # - warning, will be associated with trades, typically entry/exit, always present
    trading_log_level = getattr(logging, c.args.log_trading)
    logger = logging.getLogger('trading_loop')
    logger.setLevel(trading_log_level)
    fh = logging.FileHandler(c.log_file)
    fh.setLevel(trading_log_level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    console_log_level = getattr(logging, c.args.log_console)
    ch = logging.StreamHandler()
    ch.setLevel(console_log_level)
    formatter = logging.Formatter('%(levelname)-8s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    c.logging = logger
