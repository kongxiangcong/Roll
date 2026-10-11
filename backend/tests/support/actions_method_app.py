"""Explicit METHOD browser factory; never production configuration."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))
sys.path.insert(0, str(Path(__file__).parents[1] / 'application'))
from roll.app import create_app
from test_actions import action_package
from capability_method_app import save_package


def factory():
    directory = Path(os.environ['ROLL_DATA_DIR'])
    file = save_package(directory / 'qualification.json', action_package())
    return create_app(directory, capability_method_file=file)
