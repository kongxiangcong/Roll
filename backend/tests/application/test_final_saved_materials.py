"""Existing material selection is read-only and preserves qualification limitations."""
import json
from fastapi.testclient import TestClient
from roll.app import create_app


def test_saved_material_listing_reuses_checked_archives_without_grant_or_review(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    fixture = tmp_path / 'cases.json'
    fixture.write_text(json.dumps({'cases': [{'case_id': 'saved-unknown', 'gates': {'G4': 'INCONCLUSIVE'},
        'checks_complete': False, 'endpoint_reached': False, 'observed_value': None}]}), encoding='utf-8')
    with TestClient(create_app(tmp_path / 'data', technical_review_method_file=fixture, runtime_role='API')) as client:
        original = client.get('/api/research/method-review-materials').json()
        response = client.get('/api/research/review-materials')
        assert response.status_code == 200, response.text
        assert response.json() == original
        material = response.json()[0]
        assert material['basis_manifest']['validation_verdict'] == 'INCONCLUSIVE'
        assert client.get('/api/research/review-materials/' + material['material_id'] + '/reviews').json() == []
        assert client.get('/api/capabilities').json()['formal_judgment'] == 'DISABLED'
        assert client.get('/api/research/review-materials/' + material['material_id']).json() == material
