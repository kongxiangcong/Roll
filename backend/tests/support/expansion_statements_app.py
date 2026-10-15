"""Isolated no-network three-statement browser fixture, no grants or money."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from expansion_financial_app import app as income_app


def app():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from test_financial_statements import statements
    application=income_app();application.state.financial_statements.worker=statements
    with TestClient(application) as client:
        result=client.post('/api/market/financial/SSE:600362/income/collect',json={'idempotency_key':'browser-income','basis':'METHOD saved source replay'})
        assert result.json()['status']=='COMPLETE',result.text
    return application
