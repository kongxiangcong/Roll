"""Exact final-review browser METHOD fixture; no real authentication/provider/fit."""
import ast
import json
import os
from pathlib import Path
from roll.app import create_app


def factory():
    if os.environ.get('ROLL_ENV') != 'test': raise ValueError('FINAL_REVIEW_METHOD_TEST_ONLY')
    directory = Path(os.environ['ROLL_DATA_DIR'])
    fixture = directory.parent / 'fixture'
    fixture.mkdir(parents=True, exist_ok=False)
    tree = ast.parse((Path(__file__).parents[1] / 'application/test_technical_review.py').read_text(encoding='utf-8'))
    worker_text = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'WORKER' for t in node.targets))
    worker = fixture / 'worker.py'
    worker.write_text(worker_text, encoding='utf-8')
    # This exact fixture-generated synthetic auth file is excluded from preservation.
    auth = fixture / 'auth.json'
    auth.write_text(json.dumps({'auth_mode': 'chatgpt', 'tokens': {'access_token': 'METHOD_CASE_ONLY'}}), encoding='utf-8')
    os.environ['ROLL_CODEX_AUTH_FILE'] = str(auth)
    cases = fixture / 'cases.json'
    cases.write_text(json.dumps({'cases': [{'case_id': name, 'gates': {'G4': 'INCONCLUSIVE'},
        'checks_complete': False, 'endpoint_reached': False, 'observed_value': None} for name in ['saved-unknown-one', 'saved-unknown-two']]}), encoding='utf-8')
    return create_app(directory, codex_worker=worker, technical_review_method_file=cases, runtime_role='API')
