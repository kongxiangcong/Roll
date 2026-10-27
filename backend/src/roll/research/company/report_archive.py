"""Reuse the original archive registry metadata when bytes already exist."""
import json


def archive(evidence,content,kind,extension='raw'):
    value=evidence.archive(content,kind,extension=extension)
    with evidence.ledger.connection() as db:
        return json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?',(value['sha256'],)).fetchone()[0])
