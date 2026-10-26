import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/fundamental_valuation.py"
spec = importlib.util.spec_from_file_location("valuation", SCRIPT)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ValuationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "examples/valuation-assumptions.json").read_text(encoding="utf-8"))

    def test_constant_perpetuity_and_net_cash(self):
        result = v.dcf([100] * 5, .1, 0, 100, -200)
        self.assertAlmostEqual(result["enterprise_value"], 1000)
        self.assertAlmostEqual(result["per_share"], 12)

    def test_growing_perpetuity(self):
        result = v.dcf([102, 104.04], .1, .02, 100, 0)
        self.assertAlmostEqual(result["enterprise_value"], 102 / .08)

    def test_reverse_round_trip_and_year(self):
        fcfs = [100, 110, 120]
        forward = v.dcf(fcfs, .1, .02, 100, 200)
        reverse = v.reverse(forward["per_share"], 100, 200, .1, .02, fcfs, [.1], 1000)
        self.assertAlmostEqual(reverse["terminal_fcf_required"], 122.4)
        self.assertEqual(reverse["terminal_year"], 4)
        self.assertAlmostEqual(reverse["rows"][0]["revenue_cagr_to_terminal_year"], (1224 / 1000) ** .25 - 1)

    def test_weighting_sensitivity_and_epv(self):
        result = v.run(self.cfg)
        self.assertAlmostEqual(result["weighted_per_share"], sum(r["per_share"] * r["probability"] for r in result["scenarios"]))
        self.assertEqual(result["epv"]["per_share"], 8)
        grid = {(r["wacc"], r["terminal_g"]): r["per_share"] for r in result["sensitivity"]}
        self.assertGreater(grid[(.09, .02)], grid[(.11, .02)])
        self.assertGreater(grid[(.1, .03)], grid[(.1, .01)])

    def test_reject_invalid_inputs(self):
        for field, bad in [("shares", 0), ("wacc", .02), ("net_debt", float("nan")), ("shares", True), ("cash_flow_basis", "FCFE")]:
            with self.subTest(field=field, value=bad):
                cfg = copy.deepcopy(self.cfg)
                cfg[field] = bad
                with self.assertRaises(ValueError):
                    v.run(cfg)
        for edit in [
            lambda c: c["scenarios"][0].update(probability=.9),
            lambda c: c["scenarios"][0].update(fcf=[-10]),
            lambda c: c["scenarios"][0].update(annual_dilution=.1),
            lambda c: c["metadata"].update(shares_unit="share"),
            lambda c: c["epv"].update(excess_cash=200),
            lambda c: c["scenarios"][0].update(revenue=[100]),
        ]:
            cfg = copy.deepcopy(self.cfg)
            edit(cfg)
            with self.assertRaises(ValueError):
                v.run(cfg)

    def test_negative_early_flows_and_unattainable_reverse(self):
        self.assertTrue(v.dcf([-100, 120], .1, .02, 100, 0)["enterprise_value"] > 0)
        reverse = v.reverse(.01, 100, 0, .1, .02, [100, 100], [.1], 1000)
        self.assertEqual(reverse["status"], "no_positive_terminal_requirement")
        self.assertEqual(reverse["rows"], [])

    def test_interest_classification_equivalence(self):
        # Same economics: financing CFO 100 vs operating CFO 90, interest 10.
        self.assertEqual(v.fcff_from_cfo(100, 20, 10, .25, "financing"), 77.5)
        self.assertEqual(v.fcff_from_cfo(90, 20, 10, .25, "operating"), 77.5)
        with self.assertRaises(ValueError):
            v.fcff_from_cfo(100, 20, 10, .25, "unknown")

    def test_structured_bridge_and_ah_market_equity(self):
        cfg = copy.deepcopy(self.cfg)
        cfg.pop("net_debt")
        cfg["equity_bridge"] = [
            {"name": "debt", "amount": 300, "source": "fixture", "treatment": "deduct"},
            {"name": "cash", "amount": -100, "source": "fixture", "treatment": "add"}]
        cfg["metadata"]["listing_structure"] = "A+H"
        cfg["reverse"] = {"scenario": "base", "market_equity_value": 1500}
        result = v.run(cfg)
        self.assertEqual(result["equity_adjustment"], 200)
        self.assertEqual(result["reverse"]["market_enterprise_value"], 1700)
        self.assertEqual(result["reverse"]["rows"], [])
        cfg["reverse"] = {"scenario": "base", "price": 15}
        with self.assertRaises(ValueError):
            v.run(cfg)
        cfg["net_debt"] = 200
        with self.assertRaises(ValueError):
            v.run(cfg)

    def test_review_gate_does_not_equate_calculation_to_approval(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp) / "result.json"
            result = subprocess.run([sys.executable, str(SCRIPT), "--config", str(ROOT / "examples/valuation-assumptions.json"), "--output", str(output), "--require-reviewed"], capture_output=True)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["review"]["status"], "unreviewed")

    def test_cli_artifact_and_optimized_invalid_exit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp) / "result.json"
            result = subprocess.run([sys.executable, str(SCRIPT), "--config", str(ROOT / "examples/valuation-assumptions.json"), "--output", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(data["input_sha256"]), 64)
            bad = Path(temp) / "bad.json"
            self.cfg["shares"] = 0
            bad.write_text(json.dumps(self.cfg), encoding="utf-8")
            result = subprocess.run([sys.executable, "-O", str(SCRIPT), "--config", str(bad)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"valuation error", result.stderr)


if __name__ == "__main__":
    unittest.main()
