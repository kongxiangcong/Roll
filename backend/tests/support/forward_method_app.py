"""Explicit METHOD clock factory for real-process/browser engineering evidence only."""
import os
from datetime import datetime
from roll.app import create_app


def factory():
    if os.environ.get('ROLL_ENV') != 'test': raise RuntimeError('METHOD factory requires test profile')
    clock = datetime.fromisoformat(os.environ['ROLL_FORWARD_METHOD_NOW'])
    return create_app(review_clock=lambda:clock)
