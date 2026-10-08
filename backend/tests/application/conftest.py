from datetime import datetime, timedelta
from threading import Lock

import pytest


@pytest.fixture
def method_market_timeline(monkeypatch):
    """Only fixed-source cases: account/request/receipt precede the frozen consumer.

    One shared advancing receipt clock preserves first-request PIT rejection.
    Production time gates and OS elapsed/worker clocks are not replaced.
    """
    def freeze(consumer_at):
        consumer = datetime.fromisoformat(consumer_at)
        recorded = consumer - timedelta(minutes=1)
        consuming = False
        lock = Lock()

        def stamp():
            nonlocal recorded
            with lock:
                recorded += timedelta(microseconds=1)
                if recorded >= consumer and not consuming:
                    raise AssertionError('METHOD receipt timeline exhausted before consumer')
                return recorded.isoformat()

        def consume():
            nonlocal recorded, consuming
            with lock:
                recorded = max(recorded, consumer)
                consuming = True
                return consumer

        # These are imported wall-clock aliases, not application collaborators.
        for module in ['roll.accounts.ledger', 'roll.market.directory', 'roll.market.evidence',
                       'roll.market.resolution', 'roll.runtime.reviews']:
            monkeypatch.setattr(module + '.now', stamp)
        return consume

    return freeze
