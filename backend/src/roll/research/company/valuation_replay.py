"""Offline replay: python -m roll.research.company.valuation_replay --bundle file.json"""
import argparse
import json
from pathlib import Path
from .valuation import replay_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    args = parser.parse_args()
    result = replay_bundle(json.loads(args.bundle.read_text(encoding='utf-8')))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['matches_saved_result'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
