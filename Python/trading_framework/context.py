# a class used to contain all information we want to pass along
# most dictionaries are indexed by strategy, except what is truly linked to a symbol, like streaming state
import collections
class Context:
    # An object of this class is instanced to store information using attributes
    def __init__(self):
        self.n_exceptions = 0
        self.alive = True
        self.global_state = "IDLE"
        self.log_file = ""
        self.filename_idx = {}
        self.market_details = None  # used as a representative stock for market
        self.market_start = None
        self.market_close = None

        # a number of dictionaries, normally indexed by symbol
        self.contracts = {}
        self.details = {}
        self.tickers = {}
        self.bars = {}

        # other context information
        self.cli_commands = []
        self.ib_errors = collections.defaultdict(set)
        self.trades = []
        self.fills = []
        self.rules = {}
