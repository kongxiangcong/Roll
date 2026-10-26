"""Existing source adapters exercised through their actual public collection APIs."""
import hashlib
import json

from fastapi.testclient import TestClient
from roll.app import create_app
from test_financial_statements import statements
from test_news_ingestion import news_fixture


def setup(client, source):
    version = client.get("/api/market/list").json()["version"]
    client.post("/api/market/watch", json=dict(operation="ADD", instrument="SSE:600362", expected_list_version=version))
    client.post("/api/market/identities", json=dict(instrument="SSE:600362", exchange="SSE", board="MAIN", instrument_type="STOCK", name="江西铜业", basis="METHOD explicit company identity", effective_at="2026-10-07T00:00:00+08:00"))
    policy = next(p for p in client.get("/api/research/collection-sources").json() if p["id"] == source)
    client.post("/api/research/collection-sources/" + source + "/policy", json=dict(enabled=True, expected_revision=policy["revision"], basis="METHOD source adapter integration"))
    return client.post("/api/company-research/companies", json=dict(legal_name="江西铜业股份有限公司", aliases=["江西铜业"], jurisdiction="CN", accounting_standard="CAS", year_end="12-31", industry="NON_FINANCIAL", identity_basis="METHOD issuer identity", listings=[dict(exchange="SSE", code="600362", share_class="A", currency="CNY")])).json()


def test_existing_balance_and_cash_flow_retain_point_in_time_and_duration_basis(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role="API")) as client:
        issuer = setup(client, "akshare-financial-em")
        client.app.state.financial_statements.worker = statements
        run = client.post("/api/market/financial/SSE:600362/statements/collect", json=dict(idempotency_key="basis", basis="METHOD exact existing source adapter")).json()
        assert run["status"] == "COMPLETE", run
        results = {}
        for fact in run["facts"]:
            response = client.post("/api/company-research/materials/from-source", json=dict(company_id=issuer["company_id"], source_type="FINANCIAL_FACT", record_id=fact["fact_id"]))
            assert response.status_code == 201, response.text
            results[fact["statement"]] = response.json()
        assert results["BALANCE"]["period_start"] == results["BALANCE"]["period_end"] == "2026-06-30"
        assert results["CASH_FLOW"]["period_start"] == "2026-01-01"
        assert results["BALANCE"]["upstream"]["period_basis"] == "POINT_IN_TIME"


def test_news_association_body_receipt_and_existing_reprint_root_are_preserved(tmp_path):
    async def supplier(instrument, output):
        result = news_fixture(output)
        result["captures"][1]["received_at"] = "2026-10-15T02:00:00+00:00"
        return result
    with TestClient(create_app(tmp_path, runtime_role="API")) as client:
        issuer = setup(client, "akshare-news-em")
        client.app.state.news.worker = supplier
        run = client.post("/api/market/news/SSE:600362/collect", json=dict(idempotency_key="news", basis="METHOD named company and keyword-only negative")).json()
        assert run["status"] == "PARTIAL", run
        def import_fact(fact):
            return client.post("/api/company-research/materials/from-source", json=dict(company_id=issuer["company_id"], source_type="NEWS_FACT", record_id=fact["fact_id"]))
        accepted = import_fact(run["facts"][0])
        assert accepted.status_code == 201, accepted.text
        material = accepted.json()
        assert material["upstream"]["original_received_at"] == "2026-10-15T02:00:00+00:00"
        assert material["upstream"]["association"]["classification"] == "COMPANY_SUBJECT"
        assert material["upstream"]["body_status"] == "EXTRACTED"
        rejected = import_fact(run["facts"][1])
        assert rejected.status_code == 422 and rejected.json()["detail"]["code"] == "SOURCE_IDENTITY_UNCONFIRMED"
        async def reprint(instrument, output):
            result = await supplier(instrument, output)
            url = "https://finance.eastmoney.com/a/20261014123458.html"
            result["items"][0]["fields"]["新闻链接"] = url.replace("https:", "http:")
            result["captures"][1]["url"] = url
            raw = json.loads((output / "01.raw").read_bytes())
            raw["result"]["cmsArticleWebOld"][0]["code"] = "20261014123458"
            body = json.dumps(raw, ensure_ascii=False).encode()
            (output / "01.raw").write_bytes(body)
            result["captures"][0]["sha256"] = hashlib.sha256(body).hexdigest()
            return result
        client.app.state.news.worker = reprint
        rerun = client.post("/api/market/news/SSE:600362/collect", json=dict(idempotency_key="reprint", basis="METHOD exact article content under another URL")).json()
        assert rerun["status"] == "PARTIAL", rerun
        republished = import_fact(rerun["facts"][0]).json()
        assert republished["origin_root_id"] == material["origin_root_id"]
        assert republished["upstream"]["event"]["relation"] == "REPRINT"
