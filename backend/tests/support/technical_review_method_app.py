"""Explicit browser METHOD worker. No genuine authentication or provider network call."""
import ast
import json
import os
from pathlib import Path
from roll.app import create_app
from roll.config import data_directory


def factory():
    if os.environ.get('ROLL_ENV')!='test':raise ValueError('TECHNICAL_REVIEW_METHOD_FACTORY_TEST_ONLY')
    # Use a synthetic credential owned by this isolated browser acceptance runtime.
    directory=data_directory();config=directory/'tasks/browser-review-method';config.mkdir(parents=True,exist_ok=True)
    path=Path(__file__).parents[1]/'application/test_technical_review.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    worker_text=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WORKER' for t in node.targets))
    worker=config/'worker.py';worker.write_text(worker_text,encoding='utf-8')
    auth=config/'auth.json';auth.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}),encoding='utf-8')
    os.environ['ROLL_CODEX_AUTH_FILE']=str(auth)
    return create_app(directory,codex_worker=worker)
