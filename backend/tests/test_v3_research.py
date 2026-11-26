from argparse import ArgumentParser
from datetime import UTC, datetime, timedelta

import pytest
from roll.v3.research import register_research_commands


def research_cli(data_dir, *argv):
    parser = ArgumentParser()
    register_research_commands(parser.add_subparsers(required=True))
    args = parser.parse_args(("research", *argv))
    return args.handler(args, data_dir)


def test_imported_markdown_stays_a_draft(tmp_path):
    markdown = "---\nversion: first-draft\n---\n# 盈利与经营现金流\n\n待补公告。\n"
    path = tmp_path / "draft.md"
    path.write_text(markdown, encoding="utf-8")

    research_cli(tmp_path, "draft", "600362.SH", str(path))

    draft = research_cli(tmp_path, "show", "600362.SH", "--draft")
    assert draft["version"] == "first-draft"
    assert draft["review_status"] == "draft"
    assert draft["markdown"] == markdown
    assert research_cli(tmp_path, "show", "600362.SH") is None


def _write_draft(tmp_path, version, as_of, valid_until, thesis_status="watch"):
    path = tmp_path / f"{version}.md"
    path.write_text(
        f"""---
version: {version}
as_of: "{as_of}"
valid_until: "{valid_until}"
fundamental_gate: unknown
thesis_status: {thesis_status}
strategy_whitelist: []
invalidation_triggers:
  - id: operating-cash-flow
    source: 下一期财报的合并现金流量表
    condition: 当年累计经营现金流为负
    effect: block_new_risk
    evidence_refs: [quarterly-report]
evidence_refs: [quarterly-report]
constraint_basis:
  thesis_status:
    evidence_refs: [quarterly-report]
evidence:
  - id: quarterly-report
    title: 定期报告
    issuer: 江西铜业股份有限公司
    source: 上交所
    url: https://example.test/q3.pdf
    locator: 主要会计数据
    disclosed_at: 2026-10-29
    received_at: "{as_of}"
---
# 经营现金流
财报验证仍在进行。
""",
        encoding="utf-8",
    )
    return path


def test_published_dossier_has_an_explicit_window_and_provenance(tmp_path):
    as_of = datetime.now(UTC) - timedelta(minutes=1)
    effective_at = as_of + timedelta(days=1)
    expires = as_of + timedelta(days=15)
    path = _write_draft(tmp_path, "initial", as_of.isoformat(), expires.isoformat())
    research_cli(tmp_path, "draft", "600362.SH", str(path))

    published = research_cli(
        tmp_path, "publish", "600362.SH", "initial",
        "--reviewer", "研究者", "--effective-at", effective_at.isoformat(),
    )
    assert published["review_status"] == "published"
    assert published["constraint_basis"]["thesis_status"] == {"evidence_refs": ["quarterly-report"]}
    assert published["constraint_basis"]["fundamental_gate"] == {"confirmed_by": "研究者"}
    assert published["evidence"][0]["disclosed_at"] == "2026-10-29"
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", as_of.isoformat()) is None
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", effective_at.isoformat()) == published
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", expires.isoformat()) is None
    assert research_cli(tmp_path, "show", "600362.SH", "--version", "initial") == published


def test_publish_requires_field_basis_for_risk_permissions(tmp_path):
    now = datetime.now(UTC)
    path = _write_draft(tmp_path, "basis", (now - timedelta(minutes=1)).isoformat(),
                        (now + timedelta(days=2)).isoformat(), thesis_status="intact")
    text = path.read_text().replace("fundamental_gate: unknown", "fundamental_gate: pass")
    text = text.replace("strategy_whitelist: []", "strategy_whitelist: [daily-trend]")

    def publish(markdown):
        path.write_text(markdown, encoding="utf-8")
        research_cli(tmp_path, "draft", "600362.SH", str(path))
        return research_cli(tmp_path, "publish", "600362.SH", "basis", "--reviewer", "复核人")

    with pytest.raises(ValueError, match="constraint_basis.fundamental_gate"):
        publish(text)
    text = text.replace("constraint_basis:", "constraint_basis:\n  fundamental_gate:\n    evidence_refs: [quarterly-report]")
    with pytest.raises(ValueError, match="strategy_whitelist"):
        publish(text)
    text = text.replace("constraint_basis:", "constraint_basis:\n  strategy_whitelist:\n    rationale: 仅允许已复核的趋势规则")
    with pytest.raises(ValueError, match="thesis_status"):
        publish(text.replace("  thesis_status:\n    evidence_refs: [quarterly-report]", '  thesis_status:\n    rationale: "   "'))
    assert research_cli(tmp_path, "show", "600362.SH") is None
    result = publish(text)
    assert result["constraint_basis"]["fundamental_gate"] == {"evidence_refs": ["quarterly-report"]}
    assert result["constraint_basis"]["strategy_whitelist"] == {
        "confirmed_by": "复核人", "rationale": "仅允许已复核的趋势规则",
    }


def test_refresh_replaces_only_the_effective_version_and_keeps_the_original(tmp_path):
    now = datetime.now(UTC)
    as_of = (now - timedelta(minutes=1)).isoformat()
    expires = (now + timedelta(days=15)).isoformat()
    effective_at = (now + timedelta(days=1)).isoformat()
    next_expiry = (now + timedelta(days=7)).isoformat()
    first = _write_draft(tmp_path, "initial", as_of, expires)
    research_cli(tmp_path, "draft", "600362.SH", str(first))
    initial = research_cli(tmp_path, "publish", "600362.SH", "initial", "--reviewer", "研究者")
    assert research_cli(tmp_path, "publish", "600362.SH", "initial", "--reviewer", "研究者") == initial

    _write_draft(tmp_path, "initial", as_of, expires, thesis_status="broken")
    research_cli(tmp_path, "draft", "600362.SH", str(first))
    assert research_cli(tmp_path, "show", "600362.SH", "--draft")["thesis_status"] == "broken"
    with pytest.raises(ValueError, match="不可覆盖"):
        research_cli(tmp_path, "publish", "600362.SH", "initial", "--reviewer", "研究者")

    second = _write_draft(tmp_path, "refresh", as_of, next_expiry, thesis_status="intact")
    research_cli(tmp_path, "draft", "600362.SH", str(second))
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", effective_at) == initial
    refresh = research_cli(
        tmp_path, "publish", "600362.SH", "refresh",
        "--reviewer", "研究者", "--effective-at", effective_at,
    )
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", initial["effective_at"]) == initial
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", effective_at) == refresh
    assert research_cli(tmp_path, "show", "600362.SH", "--as-of", next_expiry) is None
    assert research_cli(tmp_path, "show", "600362.SH", "--version", "initial") == initial


def test_public_inputs_contain_only_published_evidence_for_the_requested_symbol(tmp_path):
    now = datetime.now(UTC)
    as_of = (now - timedelta(minutes=1)).isoformat()
    expires = (now + timedelta(days=15)).isoformat()
    path = _write_draft(tmp_path, "initial", as_of, expires)
    research_cli(tmp_path, "draft", "600362.SH", str(path))
    assert research_cli(tmp_path, "inputs", "600362.SH")["evidence"] == []

    publication = research_cli(tmp_path, "publish", "600362.SH", "initial", "--reviewer", "研究者")
    inputs = research_cli(tmp_path, "inputs", "600362.SH", "--as-of", publication["published_at"])
    assert inputs == {
        "symbol": "600362.SH",
        "as_of": publication["published_at"],
        "evidence": publication["evidence"],
    }
    assert research_cli(tmp_path, "inputs", "600362.SH", "--as-of", as_of)["evidence"] == []
    assert research_cli(tmp_path, "inputs", "000300.SH")["evidence"] == []
