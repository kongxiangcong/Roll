"""Reuse the pinned saved-report donor, with no fit/forecast/advance."""
import sys
from pathlib import Path


def app():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from report_method_app import factory
    return factory()
