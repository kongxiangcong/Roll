"""Explicit host-hashed METHOD acceptance factory; never a production endpoint."""
import os
from pathlib import Path
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package


def factory():
    directory = Path(os.environ['ROLL_DATA_DIR'])
    file = directory.parent / 'qualification.json'
    if not file.exists(): save_package(file, action_package())
    return create_app(directory, capability_method_file=file)
