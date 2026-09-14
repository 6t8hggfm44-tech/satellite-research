import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("reconcile_reports", Path(__file__).resolve().parents[1] / "scripts/reconcile_reports.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def packet(self, name, domain, available="2026-09-14T12:00:00Z", upstream=None):
        root = self.root / name
        root.mkdir()
        (root / "Report.md").write_text("Synthetic final report " + name)
        (root / "manifest.json").write_text("{}")
        p = {"schema_version": 1, "domain": domain, "run_id": name, "report_version": 1,
             "report_kind": "final_hypothesis_test", "generated_at_utc": "2026-09-14T11:00:00Z",
             "available_at_utc": available,
             "event_window_utc": {"start": "2026-09-07T00:00:00Z", "end": "2026-09-14T00:00:00Z"},
             "report_path": "Report.md", "manifest_path": "manifest.json", "workflow_commit": "synthetic-test",
             "sources": [{"id": name, "upstream_ids": upstream or []}], "claims": [], "supersedes": [],
             "geography": [], "actual_coverage": {}, "limitations": ["synthetic"]}
        for n in ("report", "manifest"):
            p[n + "_sha256"] = hashlib.sha256((root / p[n + "_path"]).read_bytes()).hexdigest()
        path = root / "report-envelope.json"
        path.write_text(json.dumps(p))
        return path

    def update(self, path, **changes):
        p = json.loads(path.read_text())
        p.update(changes)
        path.write_text(json.dumps(p))

    def test_future_availability_not_backfilled(self):
        p = self.packet("late", "energy", "2026-09-15T12:00:00Z")
        r = module.reconcile([p], "2026-09-14T13:00:00Z")
        self.assertEqual(r["selected"], [])
        self.assertEqual(r["excluded"][0]["reason"], "not_available_at_cutoff")

    def test_corrupt_report_rejected(self):
        p = self.packet("changed", "weather")
        (p.parent / "Report.md").write_text("changed later")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            module.read_packet(p)

    def test_shared_upstream_not_independent(self):
        a = self.packet("publisher-a", "weather", upstream=["same-measurement"])
        b = self.packet("publisher-b", "energy", upstream=["same-measurement"])
        c = module.reconcile([a, b], "2026-09-14T13:00:00Z")["comparisons"][0]
        self.assertEqual(c["independence"], "shared_dependencies")
        self.assertEqual(c["causal_link"], "not_tested")

    def test_nonoverlap_cannot_look_simultaneous(self):
        a = self.packet("old", "gev")
        b = self.packet("new", "weather")
        self.update(a, event_window_utc={"start": "2026-08-01T00:00:00Z", "end": "2026-08-07T00:00:00Z"})
        c = module.reconcile([a, b], "2026-09-14T13:00:00Z")["comparisons"][0]
        self.assertIsNone(c["event_overlap_utc"])

    def test_correction_retains_original_exclusion(self):
        a = self.packet("original", "energy")
        b = self.packet("correction", "energy")
        self.update(b, supersedes=[module.read_packet(a)["delivery_key"]], report_version=2)
        r = module.reconcile([a, b, b], "2026-09-14T13:00:00Z")
        self.assertEqual(len(r["selected"]), 1)
        self.assertEqual({x["reason"] for x in r["excluded"]}, {"duplicate", "explicitly_superseded"})

    def test_later_correction_does_not_erase_asof_original(self):
        a = self.packet("original", "energy")
        b = self.packet("correction", "energy", "2026-09-15T12:00:00Z")
        self.update(b, supersedes=[module.read_packet(a)["delivery_key"]], report_version=2)
        r = module.reconcile([a, b], "2026-09-14T13:00:00Z")
        self.assertEqual(r["selected"][0]["run_id"], "original")

    def test_path_escape_rejected(self):
        a = self.packet("bad-path", "energy")
        self.update(a, report_path="../outside.md")
        with self.assertRaisesRegex(ValueError, "escapes"):
            module.read_packet(a)


if __name__ == "__main__":
    unittest.main()
