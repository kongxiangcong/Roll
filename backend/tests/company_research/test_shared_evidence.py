import pytest
from fastapi import HTTPException
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch, CompanyCommand


def service(directory):
    ledger = Ledger(directory)
    return CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))


def company(name="江西铜业股份有限公司", aliases=None, listings=None):
    return CompanyCommand(legal_name=name, aliases=aliases or ["江西铜业"], jurisdiction="CN",
        accounting_standard="CAS", year_end="12-31", industry="NON_FINANCIAL",
        identity_basis="METHOD registration from named company disclosure; identity only",
        listings=listings or [dict(exchange="SSE", code="600362", share_class="A", currency="CNY"),
                              dict(exchange="HKEX", code="00358", share_class="H", currency="HKD")])


def test_company_resolution_keeps_ah_together_and_does_not_choose_ambiguous_name(tmp_path):
    research = service(tmp_path)
    first = research.register(company(aliases=["铜业", "江西铜业"]))
    second = research.register(company("同名铜业有限公司", ["铜业"], [dict(exchange="SZSE", code="000001", share_class="A", currency="CNY")]))
    assert research.resolve("HKEX:00358")["company"]["company_id"] == first["company_id"]
    assert research.resolve("600362")["company"]["company_id"] == first["company_id"]
    ambiguous = research.resolve("铜业")
    assert ambiguous["status"] == "AMBIGUOUS" and "company" not in ambiguous
    assert {c["company_id"] for c in ambiguous["candidates"]} == {first["company_id"], second["company_id"]}
    assert research.resolve("unknown")["status"] == "NOT_FOUND"
    assert service(tmp_path).company(first["company_id"]) == first
    assert research.evidence.ledger.account()["version"] == 0

def material_input(company_id, **overrides):
    return dict(company_id=company_id, source_id="issuer-annual", origin_root_id="issuer-annual-2025",
        source_url="https://issuer.example/annual-2025.pdf", subject_name="江西铜业股份有限公司",
        media_type="text/plain", scope="CONSOLIDATED", period_start="2025-01-01", period_end="2025-12-31",
        unit="CNY_MILLION", currency="CNY", page="12", table="Income", **overrides)


def test_import_retains_unknown_disclosure_and_same_original_is_shared_after_restart(tmp_path):
    from roll.research.company import MaterialCommand
    research = service(tmp_path)
    issuer = research.register(company())
    command = MaterialCommand(**material_input(issuer["company_id"]))
    original = b"METHOD annual report source; revenue 100"
    saved = research.import_material(command, original)
    assert saved["disclosed_at"] is None and "disclosed_at" in saved["unknown_fields"]
    assert saved["source_kind"] == "USER_IMPORT" and saved["historical_pit_eligible"] is False
    assert saved["received_at"] <= saved["consumable_at"] and saved["period_end"] == "2025-12-31"
    assert research.import_material(command, original) == saved
    recovered = service(tmp_path)
    assert recovered.material(saved["material_id"]) == saved
    assert recovered.material_bytes(saved["material_id"]) == original
    assert recovered.materials(issuer["company_id"], purpose="DAILY")["materials"] == recovered.materials(issuer["company_id"], purpose="REPORT")["materials"]
    wrong = MaterialCommand(**{**material_input(issuer["company_id"]), "subject_name": "其他公司"})
    with pytest.raises(HTTPException) as error:
        research.import_material(wrong, original)
    assert error.value.detail["code"] == "SOURCE_IDENTITY_MISMATCH"

def test_fact_restatement_and_conflict_keep_both_references_and_company_isolation(tmp_path):
    from roll.research.company import MaterialCommand, FactCommand, ConflictResolution
    research = service(tmp_path)
    issuer = research.register(company())
    other = research.register(company("其他股份有限公司", ["其他"], [dict(exchange="SZSE", code="002291", share_class="A", currency="CNY")]))
    original = research.import_material(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD original 100")
    revised = research.import_material(MaterialCommand(**{**material_input(issuer["company_id"]), "source_id": "issuer-restated"}), b"METHOD restated 90")
    common = dict(company_id=issuer["company_id"], metric="revenue", business="GROUP", period_start="2025-01-01", period_end="2025-12-31", unit="CNY_MILLION", currency="CNY", scope="CONSOLIDATED", page="12", table="Income", change_reason="Read issuer disclosure")
    first = research.add_fact(FactCommand(**common, material_id=original["material_id"], value="100"))
    restated = research.add_fact(FactCommand(**{**common, "change_reason": "Issuer restatement"}, material_id=revised["material_id"], value="90", supersedes=first["version_id"]))
    assert restated["fact_id"] == first["fact_id"] and restated["revision"] == 2
    assert restated["supersedes"] == first["version_id"]
    assert research.fact(first["version_id"])["value"] == "100"
    conflicting = research.add_fact(FactCommand(**{**common, "change_reason": "Conflicting source retained"}, material_id=original["material_id"], value="110"))
    state = research.facts(issuer["company_id"])
    assert len(state["versions"]) == 3 and state["conflicts"][0]["status"] == "UNRESOLVED"
    resolution = research.resolve_conflict(ConflictResolution(company_id=issuer["company_id"], fact_id=first["fact_id"], version_ids=[restated["version_id"], conflicting["version_id"]], selected_version_id=restated["version_id"], reason="Use explicit issuer restatement, retain counter-source"))
    assert resolution["selected_version_id"] == restated["version_id"]
    assert research.fact(conflicting["version_id"])["value"] == "110"
    assert service(tmp_path).facts(issuer["company_id"])["conflicts"][0]["status"] == "RESOLVED"
    with pytest.raises(HTTPException) as error:
        research.add_fact(FactCommand(**{**common, "company_id": other["company_id"]}, material_id=original["material_id"], value="100"))
    assert error.value.detail["code"] == "CROSS_COMPANY_REFERENCE"
    assert research.facts(other["company_id"])["versions"] == []

def test_checks_distinguish_no_new_evidence_partial_failure_and_last_success(tmp_path):
    from roll.research.company import CheckCommand, MaterialCommand
    research = service(tmp_path)
    issuer = research.register(company())
    def run(key, supplier):
        return research.check_source(CheckCommand(company_id=issuer["company_id"], source_id="issuer", requested_scopes=["annual", "announcements"], idempotency_key=key), supplier)
    first = run("first", lambda scope: [])
    assert first["status"] == "SUCCESS" and first["new_material_count"] == 0
    assert "未取得新证据" in first["meaning"]
    def partial(scope):
        if scope == "announcements":
            raise TimeoutError("METHOD upstream timeout")
        return [(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD disclosure")]
    second = run("second", partial)
    assert second["status"] == "PARTIAL" and second["failed_scopes"] == ["announcements"]
    assert second["new_material_count"] == 1 and second["last_success_at"] == first["finished_at"]
    def failed(scope):
        raise ConnectionError("METHOD unavailable")
    third = run("third", failed)
    assert third["status"] == "FAILED" and third["last_success_at"] == first["finished_at"]
    assert third["last_success_check_id"] == first["check_id"]
    assert "未完成核查" in third["meaning"]
    assert service(tmp_path).checks(issuer["company_id"])["attempts"][-1] == third
    assert run("third", lambda scope: pytest.fail("Idempotent retry must reuse receipt")) == third
    assert research.materials(issuer["company_id"])["materials"][0]["source_kind"] == "METHOD_CASE"

def test_fact_basis_mismatch_is_rejected_and_repeated_checks_do_not_invent_new_material(tmp_path):
    from roll.research.company import MaterialCommand, FactCommand, CheckCommand
    research = service(tmp_path)
    issuer = research.register(company())
    material = research.import_material(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD CNY million consolidated annual")
    common = dict(company_id=issuer["company_id"], material_id=material["material_id"], metric="revenue", business="GROUP", value="100", period_start="2025-01-01", period_end="2025-12-31", unit="CNY_MILLION", currency="CNY", scope="CONSOLIDATED", change_reason="Read disclosed number")
    for changes in [dict(unit="CNY"), dict(currency="HKD"), dict(scope="SEGMENT"), dict(period_start="2024-01-01")]:
        with pytest.raises(HTTPException) as error:
            research.add_fact(FactCommand(**{**common, **changes}))
        assert error.value.detail["code"] == "FACT_BASIS_MISMATCH"
    source = lambda scope: [(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD source unchanged")]
    first = research.check_source(CheckCommand(company_id=issuer["company_id"], source_id="issuer", requested_scopes=["annual"], idempotency_key="one"), source)
    second = research.check_source(CheckCommand(company_id=issuer["company_id"], source_id="issuer", requested_scopes=["annual"], idempotency_key="two"), source)
    assert first["new_material_count"] == 1 and second["new_material_count"] == 0


def test_storage_corruption_is_refused_by_public_record_readers(tmp_path):
    import json
    import sqlite3
    from roll.research.company import MaterialCommand, FactCommand, CheckCommand
    research = service(tmp_path)
    issuer = research.register(company())
    material = research.import_material(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD source")
    fact = research.add_fact(FactCommand(company_id=issuer["company_id"], material_id=material["material_id"], metric="revenue", business="GROUP", value="100", period_start="2025-01-01", period_end="2025-12-31", unit="CNY_MILLION", currency="CNY", scope="CONSOLIDATED", change_reason="Read source"))
    check = research.check_source(CheckCommand(company_id=issuer["company_id"], source_id="issuer", requested_scopes=["annual"], idempotency_key="one"), lambda scope: [])
    # Deliberate storage-boundary faults; assertions observe only public readers.
    for table, identifier, payload, reader in [
        ("company_research_companies", "version_id", issuer, lambda: research.company(issuer["company_id"])),
        ("company_research_facts", "version_id", fact, lambda: research.fact(fact["version_id"])),
        ("company_research_checks", "check_id", check, lambda: research.checks(issuer["company_id"]))]:
        damaged = {**payload, "created_at": "2000-01-01T00:00:00+00:00"}
        with sqlite3.connect(research.ledger.path) as db:
            db.execute(f"UPDATE {table} SET value=? WHERE {identifier}=?", (json.dumps(damaged), payload[identifier]))
        with pytest.raises(HTTPException) as error:
            reader()
        assert error.value.detail["code"] == "RESEARCH_RECORD_CORRUPT"
        with sqlite3.connect(research.ledger.path) as db:
            db.execute(f"UPDATE {table} SET value=? WHERE {identifier}=?", (json.dumps(payload), payload[identifier]))

def test_existing_market_source_is_reused_without_network_or_promoting_method_origin(tmp_path):
    import httpx
    from roll.market.directory import WatchCommand, IdentityCommand
    from roll.market.evidence import DataRequest
    from roll.research.company import ExistingSourceCommand
    ledger = Ledger(tmp_path)
    market = MarketDirectory(ledger)
    market.watch(WatchCommand(operation="ADD", instrument="SSE:600362", expected_list_version=market.listing()["version"]))
    market.identify(IdentityCommand(instrument="SSE:600362", exchange="SSE", board="MAIN", instrument_type="STOCK", name="江西铜业", basis="METHOD source identity", effective_at="2026-10-07T00:00:00+08:00"))
    calls = []
    def provider(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=b'{"rc":0,"data":{"code":"600362","klines":["2026-09-30,10,10,10,10,100,100000"]}}')
    evidence = EvidenceStore(ledger, market, httpx.MockTransport(provider))
    request = evidence.request(DataRequest(instruments=["SSE:600362"], groups=["DAILY"], purpose="OBSERVATION", start_date="2026-09-30", end_date="2026-09-30", max_calls=1))
    run = evidence.retrieve(request["request_id"])
    research = CompanyResearch(evidence)
    issuer = research.register(company())
    before = len(calls)
    command = ExistingSourceCommand(company_id=issuer["company_id"], source_type="MARKET_SNAPSHOT", record_id=run["snapshot_id"], fact_index=0)
    material = research.import_existing(command)
    assert len(calls) == before and material["source_kind"] == "METHOD_CASE"
    snapshot = evidence.get("market_evidence_snapshots", run["snapshot_id"])
    assert material["archive"]["sha256"] == snapshot["facts"][0]["raw_hash"]
    assert material["upstream"]["record_id"] == run["snapshot_id"]
    assert research.material_bytes(material["material_id"]) == evidence.raw(material["archive"]["sha256"]).read_bytes()
    assert material["disclosed_at"] is None

def test_company_research_api_import_and_download_are_independent_of_account_confirmation(tmp_path):
    import base64
    from fastapi.testclient import TestClient
    from roll.app import create_app
    with TestClient(create_app(tmp_path, runtime_role="API")) as client:
        registered = client.post("/api/company-research/companies", json=company().model_dump())
        assert registered.status_code == 201, registered.text
        issuer = registered.json()
        resolved = client.post("/api/company-research/resolve", json={"query": "HKEX:00358"})
        assert resolved.json()["company"]["company_id"] == issuer["company_id"]
        source = b"<script>source instructions are untrusted text</script>"
        imported = client.post("/api/company-research/materials", json={**material_input(issuer["company_id"]), "content_base64": base64.b64encode(source).decode()})
        assert imported.status_code == 201, imported.text
        material = imported.json()
        downloaded = client.get("/api/company-research/materials/" + material["material_id"] + "/original")
        assert downloaded.content == source
        assert downloaded.headers["x-content-type-options"] == "nosniff"
        assert downloaded.headers["content-disposition"].startswith("attachment;")
        assert client.get("/api/company-research/companies/" + issuer["company_id"] + "/materials?purpose=REPORT").json()["materials"] == [material]
        assert client.get("/api/account").json()["version"] == 0

def test_backup_restore_retains_shared_records_and_refuses_corrupt_structured_input(tmp_path):
    import io
    import json
    import sqlite3
    import zipfile
    from roll.research.company import MaterialCommand
    from roll.runtime.backups import Backups, restore_at_start
    research = service(tmp_path / "source")
    issuer = research.register(company())
    material = research.import_material(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD backed-up source")
    backups = Backups(tmp_path / "source")
    saved = backups.create()
    bundle = backups.export(saved["backup_id"])
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {a["sha256"] for a in manifest["attachments"]} == {material["archive"]["sha256"]}
    restored_backups = Backups(tmp_path / "restored")
    restored_backups.stage_restore(bundle)
    restore_at_start(restored_backups)
    restored = service(tmp_path / "restored")
    assert restored.company(issuer["company_id"]) == issuer
    assert restored.material(material["material_id"]) == material
    assert restored.material_bytes(material["material_id"]) == b"METHOD backed-up source"
    # Simulate externally corrupted JSON while leaving archive bytes intact.
    with sqlite3.connect(research.ledger.path) as db:
        bad = {**material, "company_id": "missing-company"}
        db.execute("UPDATE company_research_materials SET value=? WHERE material_id=?", (json.dumps(bad), material["material_id"]))
    with pytest.raises(HTTPException) as error:
        backups.create()
    assert error.value.detail["code"] == "RESEARCH_RECORD_CORRUPT"

def test_identity_and_material_commands_reject_incompatible_existing_identity_and_unsafe_url(tmp_path):
    from roll.market.directory import WatchCommand, IdentityCommand
    from roll.research.company import MaterialCommand
    research = service(tmp_path)
    market = research.evidence.market
    market.watch(WatchCommand(operation="ADD", instrument="SSE:600362", expected_list_version=market.listing()["version"]))
    market.identify(IdentityCommand(instrument="SSE:600362", exchange="SSE", board="MAIN", instrument_type="STOCK", name="不同公司", basis="METHOD conflicting stored identity", effective_at="2026-10-07T00:00:00+08:00"))
    with pytest.raises(HTTPException) as error:
        research.register(company())
    assert error.value.detail["code"] == "SOURCE_IDENTITY_MISMATCH"
    # Another explicit instrument has no conflicting pre-existing identity.
    issuer = research.register(company("另一家公司", ["另一家"], [dict(exchange="SZSE", code="002291", share_class="A", currency="CNY")]))
    unsafe = MaterialCommand(**{**material_input(issuer["company_id"]), "subject_name": "另一家公司", "source_url": "javascript:alert(1)"})
    with pytest.raises(HTTPException) as error:
        research.import_material(unsafe, b"METHOD original")
    assert error.value.detail["code"] == "SOURCE_URL_INVALID"

def test_public_lists_expose_pagination_without_losing_resolution_or_fact_conflicts(tmp_path):
    from roll.research.company import MaterialCommand, FactCommand
    research = service(tmp_path)
    issuer = research.register(company())
    other = research.register(company("另一公司", ["另一"], [dict(exchange="SZSE", code="002291", share_class="A", currency="CNY")]))
    assert research.companies(limit=1)["has_more"] is True
    assert research.resolve("002291")["company"]["company_id"] == other["company_id"]
    originals = [research.import_material(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD first"),
                 research.import_material(MaterialCommand(**material_input(issuer["company_id"])), b"METHOD second")]
    page = research.materials(issuer["company_id"], limit=1)
    assert page["total"] == 2 and page["has_more"] is True
    assert research.materials(issuer["company_id"], limit=1, offset=1)["materials"] == [originals[1]]
    for value, original in zip(["100", "90"], originals):
        research.add_fact(FactCommand(company_id=issuer["company_id"], material_id=original["material_id"], metric="revenue", business="GROUP", value=value, period_start="2025-01-01", period_end="2025-12-31", unit="CNY_MILLION", currency="CNY", scope="CONSOLIDATED", change_reason="METHOD opposing source"))
    facts = research.facts(issuer["company_id"], limit=1)
    assert facts["total"] == 2 and facts["has_more"] is True
    assert facts["conflicts"][0]["status"] == "UNRESOLVED"

def test_source_checks_can_reuse_existing_receipts_without_counting_unchanged_captures_as_new(tmp_path):
    import httpx
    from roll.market.directory import WatchCommand, IdentityCommand
    from roll.market.evidence import DataRequest
    from roll.research.company import ExistingSourceCommand, CheckCommand
    ledger = Ledger(tmp_path)
    market = MarketDirectory(ledger)
    market.watch(WatchCommand(operation="ADD", instrument="SSE:600362", expected_list_version=market.listing()["version"]))
    market.identify(IdentityCommand(instrument="SSE:600362", exchange="SSE", board="MAIN", instrument_type="STOCK", name="江西铜业", basis="METHOD identity", effective_at="2026-10-07T00:00:00+08:00"))
    evidence = EvidenceStore(ledger, market, httpx.MockTransport(lambda request: httpx.Response(200, content=b'{"rc":0,"data":{"code":"600362","klines":["2026-09-30,10,10,10,10,100,100000"]}}')))
    request = evidence.request(DataRequest(instruments=["SSE:600362"], groups=["DAILY"], purpose="OBSERVATION", start_date="2026-09-30", end_date="2026-09-30", max_calls=1))
    research = CompanyResearch(evidence)
    issuer = research.register(company())
    captures = []
    for key in ["first", "second"]:
        run = evidence.retrieve(request["request_id"])
        reference = ExistingSourceCommand(company_id=issuer["company_id"], source_type="MARKET_SNAPSHOT", record_id=run["snapshot_id"])
        captures.append(research.check_source(CheckCommand(company_id=issuer["company_id"], source_id="eastmoney-daily", requested_scopes=["2026-09-30"], idempotency_key=key), lambda scope: [reference]))
    assert captures[0]["status"] == captures[1]["status"] == "SUCCESS"
    assert captures[0]["new_material_count"] == 1 and captures[1]["new_material_count"] == 0
    assert captures[0]["material_ids"] == captures[1]["material_ids"]
    assert captures[0]["source_receipts"][0]["record_id"] != captures[1]["source_receipts"][0]["record_id"]
