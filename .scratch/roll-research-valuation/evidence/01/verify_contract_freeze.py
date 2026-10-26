"""Verify the ticket-01 reference freeze and enumerate every original gate call.

This is a documentation integrity check, not a product/valuation acceptance test.
It only reads the in-repository frozen snapshot, so it works without the source checkout.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FROZEN = ROOT / 'docs/reference/deep-dive-research/20261026'
HERE = Path(__file__).resolve().parent


def gate_rules():
    source = (FROZEN / 'scripts/check_gates.py').read_text(encoding='utf-8-sig')
    result = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add' and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'r' and len(node.args) >= 3):
            continue
        gate = ast.literal_eval(node.args[0])
        level = next((ast.literal_eval(k.value) for k in node.keywords if k.arg == 'level'), 'fail')
        result.append({
            'rule_id': f'ddr-check-gates-{node.lineno}',
            'source_path': 'scripts/check_gates.py', 'source_line': node.lineno,
            'source_gate': gate, 'source_name_expression': ast.get_source_segment(source, node.args[1]),
            'source_severity': level,
            'roll_ticket': '08' if gate != '可移植性' else '08/09/12',
            'roll_action': ('ADAPT_TO_ROLL_PACKAGE_CHECK; skill-only checks NOT_APPLICABLE with reason'
                            if gate == '可移植性' else
                            'PRESERVE_CONDITIONAL_CHECK_AND_SEVERITY; material gaps remain FAIL/UNKNOWN and permit PARTIAL only'),
            'roll_result_fields': ['rule_id', 'source_hash', 'source_line', 'applies', 'severity', 'outcome', 'evidence', 'reason'],
            'semantic_mapping': 'docs/research/company-report-template-map.md#原质量规则逐项适配',
        })
    return sorted(result, key=lambda r: r['source_line'])


def main():
    entries = json.loads((FROZEN / 'manifest.json').read_text(encoding='utf-8-sig'))
    for entry in entries:
        raw = (FROZEN / entry['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry['sha256'] or len(raw) != entry['bytes']:
            raise ValueError(f"Frozen file changed: {entry['path']}")
    rules = gate_rules()
    saved = json.loads((HERE / 'gate-rule-map.json').read_text(encoding='utf-8'))
    if rules != saved:
        raise ValueError('Gate call mapping differs from the frozen source')
    print(json.dumps({'frozen_files_checked': len(entries), 'gate_call_sites_mapped': len(rules),
                      'source_checkout_required': False, 'status': 'PASS'}, indent=2))


if __name__ == '__main__':
    main()
