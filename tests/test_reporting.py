"""Offline report-package integration tests using explicitly synthetic evidence."""

from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from satresearch.reporting import build_report, coverage_rows, screen
from satresearch.satellites import normalize_satellites
from satresearch.storage import Store


START = 1704067200.0  # Synthetic 2024-01-01 UTC window, not a historical claim.
END = START + 3600


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data_dir = self.root / "data"
        self.config = {
            "baseline_days": 7,
            "regions": [{"id": "synthetic-region", "bbox": [10, 50, 40, 70]}],
            "aircraft_interval_s": 60,
            "aircraft_detectors": {},
            "satellite_detectors": {},
            "max_analysis_records": 100,
        }
        self.bodies = {}

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def read(path):
        return json.loads(Path(path).read_text())

    def capture(self, store, timestamp, body=b'{"synthetic":true}', source="aircraft:synthetic-region",
                status="available", warnings=None):
        reference = store.save_capture(source, body, {
            "retrieved_at": timestamp, "status": status,
            "http_status": 200 if status == "available" else None,
            "warnings": warnings or [], "coverage": None,
            "request": {"fixture": "offline synthetic report test"},
        })
        self.bodies[reference] = body
        return reference

    @staticmethod
    def aircraft(index, timestamp, reference, **changes):
        record = {
            "observation_id": "synthetic-" + str(index), "entity_id": "synthetic-aircraft",
            "timestamp": timestamp, "snapshot_at": timestamp + 1,
            "lat": 60.0, "lon": 20.0, "altitude_m": 9000.0,
            "altitude_type": "barometric", "groundspeed_mps": 230.0,
            "track_deg": 90.0, "position_source": "adsb_icao",
            "region": "synthetic-region", "source_id": "fixture-publisher",
            "position_age_s": 1.0, "quality_flags": [], "raw_ref": reference,
        }
        record.update(changes)
        return record

    def seed_aircraft(self, include_controls=True):
        with Store(self.data_dir) as store:
            first = self.capture(store, START + 61, b'{"synthetic":"position-one"}')
            second = self.capture(store, START + 91, b'{"synthetic":"position-two"}')
            repeat = self.capture(store, START + 151, self.bodies[first])
            rows = [self.aircraft(1, START + 60, first),
                    self.aircraft(2, START + 90, second, lon=25.0)]
            store.add_observations("aircraft", rows)
            store.add_observations("aircraft", [dict(
                rows[0], raw_ref=repeat, snapshot_at=START + 151, position_age_s=91,
                quality_flags=["stale_position"],
            )])
            if include_controls:
                control = self.capture(store, START + 121, b'{"synthetic":"uncited-control"}')
                store.add_observations("aircraft", [self.aircraft(
                    "control", START + 120, control, entity_id="synthetic-control", lon=23.0,
                )])
                for day in (1, 2, 3):
                    reference = self.capture(store, START - day * 86400 + 31,
                                             ("synthetic baseline " + str(day)).encode())
                    store.add_observations("aircraft", [
                        self.aircraft("baseline-{}-{}".format(day, index),
                                      START - day * 86400 + index * 30, reference,
                                      lon=20 + index * 0.01)
                        for index in (0, 1)
                    ])
        return {first, second, repeat}

    def report(self, name="report", config=None):
        folder = self.root / name
        summary = build_report(self.data_dir, config or self.config, folder, START, END)
        return folder, summary

    def replay(self, folder):
        environment = dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, "-B", str(folder / "replay" / "replay.py")],
            cwd=str(self.root), env=environment, capture_output=True, text=True, timeout=30,
        )

    def manifest_errors(self, folder):
        errors = []
        for item in self.read(folder / "manifest.json")["files"]:
            path = folder / item["path"]
            if (not path.is_file() or path.stat().st_size != item["bytes"] or
                    hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]):
                errors.append(item["path"])
        return errors

    def test_empty_store_produces_honest_complete_package(self):
        folder, summary = self.report()
        self.assertEqual(summary["candidate_events"], 0)
        self.assertEqual(summary["input_records"], {"aircraft": 0, "satellite": 0})
        self.assertEqual(summary["baseline"]["status"], "warming_up")
        coverage = self.read(folder / "coverage.json")
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]["attempts"], 0)
        self.assertEqual(coverage[0]["expected_poll_slots"], 60)
        self.assertEqual(coverage[0]["status"], "no_saved_data")
        text = (folder / "Report.md").read_text()
        self.assertIn("no saved data, not no traffic", text)
        self.assertIn("No candidate met", text)
        self.assertIn("Not calibrated", summary["calibration"])
        self.assertEqual(self.manifest_errors(folder), [])
        with self.assertRaises(FileExistsError):
            self.report()

    def test_partial_capture_coverage_separates_fresh_stale_and_failed(self):
        with Store(self.data_dir) as store:
            self.capture(store, START + 1)
            self.capture(store, START + 61, warnings=["stale_or_unknown_feed_time"])
            self.capture(store, START + 121, body=b"", status="request_failed")
        folder, summary = self.report()
        coverage = self.read(folder / "coverage.json")[0]
        self.assertEqual(summary["collection_requests"], 3)
        self.assertEqual(coverage["attempts"], 3)
        self.assertEqual(coverage["usable_snapshots"], 2)
        self.assertEqual(coverage["fresh_snapshots"], 1)
        self.assertEqual(coverage["status"], "partial_sampling")
        self.assertEqual(coverage["expected_poll_slots"], 60)

    def test_inclusive_coverage_keeps_capture_at_report_endpoint(self):
        capture = {"source_id": "aircraft:synthetic-region", "retrieved_at": END,
                   "status": "available", "warnings": []}
        rows = coverage_rows([capture], self.config, START, END)
        self.assertEqual(sum(row["attempts"] for row in rows), 1,
                         "The report declares inclusive bounds; an endpoint capture must not disappear")

    def test_latest_review_is_retained_without_counting_old_actions(self):
        self.seed_aircraft()
        with Store(self.data_dir) as store:
            events = screen(store, self.config, START, END)[0]
            self.assertEqual(len(events), 1)
            event_id = events[0]["event_id"]
            store.review(event_id, "needs_more_data", "Need independent evidence")
            store.review(event_id, "explained", "Synthetic explanation supplied")
            store.save_events([{"event_id": "unrelated", "timestamp": START - 86400}])
            store.review("unrelated", "dismissed", "Outside this report")
        folder, summary = self.report()
        self.assertEqual(summary["review_counts"], {"explained": 1})
        event = self.read(folder / "events.json")[0]
        self.assertEqual(event["event_id"], event_id)
        self.assertEqual(event["review_note"], "Synthetic explanation supplied")
        self.assertEqual(event["review_status"], "explained")
        self.assertEqual(len(self.read(folder / "reviews.json")), 3)
        replay = self.replay(folder)
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)

    def test_candidate_exports_every_capture_reference_and_original_bytes(self):
        expected_refs = self.seed_aircraft()
        folder, summary = self.report()
        self.assertEqual(summary["candidate_events"], 1)
        observations = self.read(folder / "observations.json")
        self.assertEqual({r["observation_id"] for r in observations}, {"synthetic-1", "synthetic-2"})
        linked = {ref for row in observations for ref in row["raw_refs"]}
        self.assertEqual(linked, expected_refs)
        register = self.read(folder / "evidence-register.json")
        self.assertEqual({item["capture_id"] for item in register}, expected_refs)
        self.assertEqual(len({item["exported_path"] for item in register}), 2)
        for item in register:
            body = (folder / item["exported_path"]).read_bytes()
            self.assertEqual(body, self.bodies[item["capture_id"]])
            self.assertEqual(hashlib.sha256(body).hexdigest(), item["body_sha256"])

    def test_frozen_inputs_replay_independently_and_manifest_detects_tampering(self):
        self.seed_aircraft()
        folder, summary = self.report()
        frozen = json.loads(gzip.decompress((folder / "replay" / "inputs.json.gz").read_bytes()))
        self.assertEqual(len(frozen["aircraft"]), 3)
        self.assertEqual(len(frozen["aircraft_baseline"]), 6)
        self.assertIn("synthetic-control", {r["observation_id"] for r in frozen["aircraft"]})
        manifest = self.read(folder / "manifest.json")
        self.assertEqual({item["path"] for item in manifest["files"]},
                         {str(path.relative_to(folder)) for path in folder.rglob("*")
                          if path.is_file() and path.name != "manifest.json"})
        self.assertEqual(self.manifest_errors(folder), [])
        independent = self.root / "independent-copy"
        shutil.copytree(folder, independent)
        with Store(self.data_dir) as store:
            reference = self.capture(store, START + 151, b"later synthetic data")
            store.add_observations("aircraft", [self.aircraft(3, START + 150, reference, lon=30.0)])
        replay = self.replay(independent)
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
        self.assertEqual(json.loads(replay.stdout)["events"], summary["candidate_events"])
        self.assertTrue(json.loads(replay.stdout)["passed"])
        expected = self.read(independent / "events.json")
        expected[0]["metrics"]["max_implied_speed_mps"] += 1
        (independent / "events.json").write_text(json.dumps(expected))
        rejected = self.replay(independent)
        self.assertEqual(rejected.returncode, 1, rejected.stdout + rejected.stderr)
        self.assertFalse(json.loads(rejected.stdout)["passed"])
        self.assertEqual(self.manifest_errors(independent), ["events.json"])

    def test_record_caps_are_flagged_and_replayed_as_partial_screening(self):
        self.seed_aircraft()
        config = dict(self.config, max_analysis_records=2)
        folder, summary = self.report(config=config)
        self.assertEqual(summary["input_records"]["aircraft"], 2)
        self.assertEqual(set(summary["baseline"]["truncated_input_sets"]),
                         {"aircraft_current", "aircraft_baseline"})
        self.assertEqual(summary["candidate_events"], 1)
        event = self.read(folder / "events.json")[0]
        self.assertTrue(any("screening is partial" in value for value in event["limitations"]))
        self.assertIn("capped sets: aircraft_current, aircraft_baseline", (folder / "Report.md").read_text())
        replay = self.replay(folder)
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)

    def test_same_satellite_id_preserves_current_and_baseline_capture_contexts(self):
        epoch = datetime.fromtimestamp(START - 5 * 86400, timezone.utc).isoformat().replace("+00:00", "Z")
        omm = {"NORAD_CAT_ID": 123456, "OBJECT_NAME": "SYNTHETIC OBJECT", "EPOCH": epoch,
               "MEAN_MOTION": 15.0, "INCLINATION": 51.0, "ECCENTRICITY": 0.001,
               "RA_OF_ASC_NODE": 100.0, "ARG_OF_PERICENTER": 20.0, "MEAN_ANOMALY": 30.0,
               "CENTER_NAME": "EARTH", "REF_FRAME": "TEME", "TIME_SYSTEM": "UTC",
               "MEAN_ELEMENT_THEORY": "SGP4"}
        references = []
        with Store(self.data_dir) as store:
            for snapshot in (START - 100, START + 100, END + 100):
                reference = self.capture(store, snapshot, json.dumps(omm).encode(), source="satellite:synthetic")
                references.append(reference)
                records, warnings = normalize_satellites(omm, "satellite:synthetic", snapshot, reference)
                self.assertEqual(warnings, [])
                store.add_observations("satellite", records)
            self.assertEqual(store.stats()["observations"], 1)
        folder, summary = self.report()
        self.assertEqual(summary["input_records"]["satellite"], 1)
        self.assertEqual(summary["candidate_events"], 1)
        cited = self.read(folder / "observations.json")
        self.assertEqual(len(cited), 2)
        self.assertEqual(len({row["observation_id"] for row in cited}), 1)
        self.assertEqual({row["snapshot_at"] for row in cited}, {START - 100, START + 100})
        self.assertEqual({ref for row in cited for ref in row["raw_refs"]}, set(references[:2]))
        self.assertEqual({item["capture_id"] for item in self.read(folder / "evidence-register.json")},
                         set(references[:2]))
        replay = self.replay(folder)
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)


if __name__ == "__main__":
    unittest.main()
