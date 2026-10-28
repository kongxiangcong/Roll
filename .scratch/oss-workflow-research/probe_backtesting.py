"""Bounded offline reproduction of the upstream quickstart and input boundary."""
import hashlib
import importlib.metadata
import json
import socket
import time
import warnings
from pathlib import Path

from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import GOOG, SMA


def no_network(*args, **kwargs):
    raise RuntimeError("NETWORK_DISABLED_FOR_OFFLINE_PROBE")


socket.create_connection = no_network
socket.socket.connect = no_network


class SmaCross(Strategy):
    def init(self):
        self.ma1 = self.I(SMA, self.data.Close, 10)
        self.ma2 = self.I(SMA, self.data.Close, 20)

    def next(self):
        if crossover(self.ma1, self.ma2):
            self.buy()
        elif crossover(self.ma2, self.ma1):
            self.sell()


def run(frame):
    with warnings.catch_warnings(record=True) as caught:
        result = Backtest(frame, SmaCross, commission=.002, exclusive_orders=True).run()
    return {
        "trades": int(result["# Trades"]),
        "return_percent": float(result["Return [%]"]),
        "buy_hold_return_percent": float(result["Buy & Hold Return [%]"]),
        "max_drawdown_percent": float(result["Max. Drawdown [%]"]),
        "warnings": [str(item.message) for item in caught],
    }


started = time.perf_counter()
evidence = {
    "purpose": "UPSTREAM_OFFLINE_EXAMPLE_NOT_ROLL_OR_A_SHARE_ACCEPTANCE",
    "package": "backtesting",
    "version": importlib.metadata.version("backtesting"),
    "data": "upstream packaged GOOG historical sample; not current Roll data",
    "rows": len(GOOG),
    "start": str(GOOG.index.min()),
    "end": str(GOOG.index.max()),
    "data_csv_sha256": hashlib.sha256(GOOG.to_csv().encode()).hexdigest(),
    "network": "socket connection attempts rejected during probe",
    "full_ohlcv": run(GOOG),
    "without_volume": run(GOOG.drop(columns=["Volume"])),
}
broken = GOOG.copy()
broken.loc[broken.index[30], "Close"] = float("nan")
try:
    run(broken)
except ValueError as exc:
    evidence["missing_close"] = {"rejected": True, "error": str(exc)}
else:
    evidence["missing_close"] = {"rejected": False}
evidence["elapsed_seconds"] = round(time.perf_counter() - started, 4)
path = Path(__file__).with_name("backtesting-evidence.json")
path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps(evidence, indent=2))
