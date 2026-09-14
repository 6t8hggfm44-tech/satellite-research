import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

from satresearch.storage import Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name)
        self.store = Store(self.data_dir)

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def capture(self, timestamp=100, body=b'{"states":[]}'):
        return self.store.save_capture("fixture", body, {
            "retrieved_at": timestamp, "http_status": 200,
            "request": {"region": "synthetic"}, "coverage": None,
        })

    def observation(self, capture_id, **changes):
        record = {"observation_id": "obs-1", "entity_id": "synthetic-1",
                  "source_id": "fixture", "timestamp": 90, "raw_ref": capture_id,
                  "latitude": 0, "longitude": None, "altitude": None,
                  "quality": 0}
        record.update(changes)
        return record

    def test_reopen_compressed_raw_and_nulls(self):
        body = b'{"states":[]}' * 1000 + b"\x00\xff"
        capture_id = self.capture(body=body)
        self.assertEqual(self.store.add_observations("aircraft", [self.observation(capture_id)]), 1)
        self.store.close()
        self.store = Store(self.data_dir)
        self.assertEqual(self.store.read_capture(capture_id), body)
        capture = self.store.captures(100, 100)[0]
        self.assertEqual(capture["body_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(capture["raw_ref"], capture_id)
        compressed = (self.data_dir / capture["raw_path"]).read_bytes()
        self.assertEqual(gzip.decompress(compressed), body)
        self.assertEqual(compressed[4:8], b"\x00" * 4)
        self.assertLess(capture["stored_bytes"], capture["body_bytes"])
        record = self.store.observations("aircraft", 90, 90)[0]
        self.assertIsNone(record["longitude"])
        self.assertIsNone(record["altitude"])
        self.assertEqual(record["quality"], 0)
        self.assertNotIn("velocity", record)
        self.assertIsNone(capture["coverage"])
        self.assertTrue(self.store.verify()["ok"])

    def test_capture_attempts_share_blob_and_observation(self):
        first = self.capture(100)
        self.assertEqual(self.capture(100), first)
        second = self.capture(101)
        self.assertNotEqual(first, second)
        self.assertEqual(self.store.add_observations("aircraft", [self.observation(first)]), 1)
        self.assertEqual(self.store.add_observations("aircraft", [self.observation(second)]), 0)
        self.assertEqual(self.store.add_observations("aircraft", [self.observation(first)]), 0)
        observations = self.store.observations("aircraft", 0, 200)
        self.assertEqual(len(observations), 1)
        self.assertEqual(set(observations[0]["raw_refs"]), {first, second})
        self.assertEqual(observations[0]["raw_ref"], first)
        stats = self.store.stats()
        self.assertEqual(stats["captures"], 2)
        self.assertEqual(stats["raw_blobs"], 1)
        self.assertEqual(stats["observation_captures"], 2)
        self.assertEqual(stats["observations_by_domain"], {"aircraft": 1})
        self.assertEqual(stats["raw_bytes"], stats["stored_bytes"])

    def test_normalized_revisions_are_not_overwritten(self):
        first = self.capture(100)
        second = self.capture(101, b"revision")
        self.store.add_observations("aircraft", [self.observation(first)])
        self.store.add_observations("aircraft", [self.observation(second, longitude=1)])
        records = self.store.observations("aircraft", 0, 200)
        self.assertEqual(len(records), 2)
        self.assertEqual({r["longitude"] for r in records}, {None, 1})
        self.assertEqual(len({r["revision_id"] for r in records}), 2)
        self.assertTrue(self.store.verify()["ok"])

    def test_capture_context_dedupes_without_leaking_future_baselines(self):
        first = self.capture(100)
        second = self.capture(200)
        future = self.capture(300)
        for index, (capture_id, snapshot) in enumerate(((first, 100), (second, 200), (future, 300))):
            count = self.store.add_observations("satellite", [self.observation(
                capture_id, timestamp=10, epoch=10, snapshot_at=snapshot,
                first_snapshot_at=snapshot, position_age_s=snapshot - 10,
                feed_timestamp=snapshot - 1,
            )])
            self.assertEqual(count, 1 if index == 0 else 0)
        self.assertEqual(self.store.stats()["observations"], 1)
        self.assertEqual(self.store.stats()["observation_captures"], 3)
        baseline = self.store.observations("satellite", 50, 150, time_field="snapshot_at")[0]
        self.assertEqual(baseline["snapshot_at"], 100)
        self.assertEqual(baseline["first_snapshot_at"], 100)
        self.assertEqual(baseline["position_age_s"], 90)
        self.assertEqual(baseline["feed_timestamp"], 99)
        self.assertEqual(baseline["raw_ref"], first)
        self.assertEqual(baseline["raw_refs"], [first])
        current = self.store.observations("satellite", 150, 250, time_field="snapshot_at")[0]
        self.assertEqual(current["snapshot_at"], 200)
        self.assertEqual(current["first_snapshot_at"], 200)
        self.assertEqual(current["raw_refs"], [second])
        self.assertEqual(current["timestamp"], 10)
        self.assertEqual(current["epoch"], 10)
        all_records = self.store.observations("satellite", None, None, time_field="snapshot_at")
        self.assertEqual(all_records[0]["snapshot_at"], 300)
        self.assertEqual(all_records[0]["first_snapshot_at"], 100)
        self.assertEqual(set(all_records[0]["raw_refs"]), {first, second, future})
        self.assertTrue(self.store.verify()["ok"])

    def test_stale_redisplay_does_not_replace_fresh_measurement_context(self):
        fresh, stale = self.capture(100), self.capture(200)
        flags = ["unknown_field_age"]
        first = self.observation(fresh, snapshot_at=100, position_age_s=10, quality_flags=flags)
        second = self.observation(stale, snapshot_at=200, position_age_s=110,
                                  quality_flags=flags + ["stale_position", "stale_feed"])
        self.assertEqual(self.store.add_observations("aircraft", [first]), 1)
        self.assertEqual(self.store.add_observations("aircraft", [second]), 0)
        measured = self.store.observations("aircraft", 90, 90)[0]
        self.assertEqual(measured["raw_ref"], fresh)
        self.assertEqual(measured["position_age_s"], 10)
        self.assertEqual(measured["quality_flags"], flags)
        self.assertEqual(set(measured["raw_refs"]), {fresh, stale})
        displayed = self.store.observations("aircraft", 150, 250, time_field="snapshot_at")[0]
        self.assertEqual(displayed["raw_ref"], stale)
        self.assertIn("stale_position", displayed["quality_flags"])
        self.assertEqual(displayed["raw_refs"], [stale])
        self.assertTrue(self.store.verify()["ok"])

    def test_limit_applies_after_time_eligibility(self):
        capture_id = self.capture(100)
        records = [self.observation(capture_id, observation_id="old-" + str(index),
                                    timestamp=index, epoch=index, snapshot_at=10)
                   for index in range(1, 5)]
        records.append(self.observation(capture_id, observation_id="current", timestamp=90,
                                        epoch=25, snapshot_at=100))
        self.store.add_observations("satellite", records)
        selected = self.store.observations("satellite", 50, 150, time_field="snapshot_at", limit=1)
        self.assertEqual([r["observation_id"] for r in selected], ["current"])
        selected = self.store.observations("satellite", 1, 90, limit=3)
        self.assertEqual([r["timestamp"] for r in selected], [1, 2, 3])
        selected = self.store.observations("satellite", 25, 25, time_field="epoch", limit=1)
        self.assertEqual([r["observation_id"] for r in selected], ["current"])
        for invalid in (True, 0, -1, 1.5):
            with self.assertRaises(ValueError):
                self.store.observations("satellite", None, None, limit=invalid)

    def test_transaction_rolls_back_batch_with_unknown_capture(self):
        first = self.capture()
        with self.assertRaises(ValueError):
            self.store.add_observations("aircraft", [
                self.observation(first),
                self.observation("unknown", observation_id="bad"),
            ])
        self.assertEqual(self.store.stats()["observations"], 0)
        self.assertEqual(self.store.stats()["observation_captures"], 0)
        self.assertEqual(self.store.stats()["captures"], 1)

    def test_time_fields_stay_distinct_and_unknown_is_not_zero(self):
        capture_id = self.capture()
        self.store.add_observations("satellite", [
            self.observation(capture_id, epoch=25),
            self.observation(capture_id, observation_id="unknown-time", timestamp=None, epoch=None),
        ])
        self.assertEqual(len(self.store.observations("satellite", 90, 90)), 1)
        self.assertEqual(len(self.store.observations("satellite", 25, 25, time_field="epoch")), 1)
        self.assertEqual(self.store.observations("satellite", 25, 25), [])
        self.assertEqual(len(self.store.observations("satellite", None, None)), 2)
        self.assertEqual(self.store.observations("satellite", 0, 0, time_field="epoch"), [])
        self.assertEqual(self.store.captures(90, 90), [])
        with self.assertRaises(ValueError):
            self.store.observations("satellite", 20, 10)

    def test_review_history_survives_machine_event_refresh_and_reopen(self):
        self.assertEqual(self.store.save_events([{"id": "event-1", "start": 80, "end": 120,
                                                 "score": 1}]), 1)
        self.store.review("event-1", "needs_more_data", "Requires a comparator")
        self.store.review("event-1", "explained", "Known source transition")
        self.assertEqual(self.store.save_events([{"event_id": "event-1", "start": 80,
                                                 "end": 125, "score": 2,
                                                 "review_status": "confirmed_data_anomaly"}]), 0)
        self.store.close()
        self.store = Store(self.data_dir)
        self.assertEqual(len(self.store.reviews()), 2)
        event = self.store.events(100, 100)[0]
        self.assertEqual(event["score"], 2)
        self.assertEqual(event["review_status"], "explained")
        self.assertEqual(event["review_note"], "Known source transition")
        self.assertEqual(self.store.events(126, 150), [])
        self.assertTrue(self.store.verify()["ok"])

    def test_invalid_reviews_and_unknown_events_are_rejected(self):
        self.store.save_events([{"event_id": "event-1", "timestamp": 100}])
        with self.assertRaises(ValueError):
            self.store.review("event-1", "confirmed_military_attack", "not a supported label")
        with self.assertRaises(ValueError):
            self.store.review("missing", "dismissed", "unknown event")
        self.assertEqual(self.store.reviews(), [])

    def test_raw_immutability_and_tamper_detection(self):
        body = b"original response"
        capture_id = self.capture(body=body)
        capture = self.store.captures(None, None)[0]
        path = self.data_dir / capture["raw_path"]
        original = path.read_bytes()
        self.capture(body=body)
        self.assertEqual(path.read_bytes(), original)
        path.write_bytes(gzip.compress(b"modified response", mtime=0))
        with self.assertRaises(OSError):
            self.capture(body=body)
        with self.assertRaises(OSError):
            self.store.read_capture(capture_id)
        self.assertEqual(gzip.decompress(path.read_bytes()), b"modified response")
        verification = self.store.verify()
        self.assertFalse(verification["ok"])
        self.assertTrue(any("raw hash" in e for e in verification["errors"]))

    def test_verify_detects_missing_raw_and_broken_provenance_link(self):
        capture_id = self.capture()
        self.store.add_observations("aircraft", [self.observation(capture_id)])
        raw_path = self.data_dir / self.store.captures(None, None)[0]["raw_path"]
        raw_path.unlink()
        with self.store.connection:
            self.store.connection.execute("DELETE FROM observation_captures")
        errors = self.store.verify()["errors"]
        self.assertTrue(any("missing or unsafe raw" in e for e in errors))
        self.assertTrue(any("missing observation capture link" in e for e in errors))

    def test_wal_and_context_manager(self):
        self.assertEqual(self.store.connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.store.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.store.connection.execute("PRAGMA busy_timeout").fetchone()[0], 30000)
        with Store(self.data_dir) as second:
            capture_id = self.capture()
            self.assertEqual(second.read_capture(capture_id), b'{"states":[]}')


if __name__ == "__main__":
    unittest.main()
