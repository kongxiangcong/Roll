"""Build the fixed ticket19 engineering model in its own persistent virtual lab."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend/src'))
from roll.app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT/'.roll-data/synthetic19')
    args = parser.parse_args()
    app = create_app(args.data_dir.resolve())
    result = app.state.development.create()
    print(json.dumps({'data_dir': str(args.data_dir.resolve()), 'run': result}, ensure_ascii=False, indent=2))
    if result['status'] != 'ENGINEERING_COMPLETE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
