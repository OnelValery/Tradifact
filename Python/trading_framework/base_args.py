import argparse

# A set of defaults, they can be edited to reflect other preferences, return a parser that can be updated
default_ipaddr = "127.0.0.1"
default_port = 7497  # this the default port for paper account, it may be updated to reflect the preferred port
default_market_tz = "US/Eastern"  # market timezone, Eastern maps to NYC, used for stocks trading.
default_log_lib = "WARNING"
default_log_trading = "INFO"
default_log_console = "WARNING"


def base_args(description="trading framework", default_client=0, default_input_file="stocks.xlsx"):
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument("-i", "--ipaddr", dest="ipaddr", default=default_ipaddr, type=str,
                        help="IP address to use, default is local PC: " + default_ipaddr)
    parser.add_argument("-p", "--port", dest="port", default=default_port, type=int,
                        help="IP port to use, default: " + str(default_port))
    parser.add_argument("-c", "--client", dest="client", default=default_client, type=int,
                        help="Client number to use, default: " + str(default_client))

    parser.add_argument("--market_tz", default=default_market_tz, type=str,
                        help="Timezone of market time, default: " + default_market_tz)
    parser.add_argument("-f", "--input_file", dest="input_file", default=default_input_file, type=str,
                        help="Name of input file identifying stocks to track, default: " + default_input_file)

    parser.add_argument("--log_lib", default=default_log_lib, type=str,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Log level for the library code, default: " + default_log_lib)
    parser.add_argument("--log_trading", default=default_log_trading, type=str,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Log level for the trading code, default: " + default_log_trading)
    parser.add_argument("--log_console", default=default_log_console, type=str,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Log level shown on the console, default: " + default_log_console)

    parser.add_argument("--test_right_now", action="store_true",
                        help="Only used for testing, ignore normal time boundaries and other shortcuts")
    parser.add_argument("--debug", help="Do whatever is needed for debug, do not use unless asked", action="store_true")
    parser.add_argument("--fail_fast", help="Fail at first exception instead of trying to recover", action="store_true")

    return parser
