"""Independent normalization contract regressions with synthetic payloads.

These cover provenance boundaries and valid controls, without network requests.
"""

import copy
import json
import math
import unittest

from satresearch.aircraft import screen_aircraft
from satresearch.normalize import normalize_snapshot, normalize_trace


NOW = 1710000000.0
REGION = {"id": "test-region", "bbox": [10, 50, 40, 70]}


def vector(timestamp=NOW, lon=24.0, **changes):
    row = ["abc123", "TEST", "", timestamp, timestamp, lon, 60.0,
           9000.0, False, 230.0, 90.0, 0, None, 9200.0, "1000", False, 0]
    indexes = {"entity": 0, "timestamp": 3, "lon": 5, "lat": 6,
               "altitude": 7, "on_ground": 8, "speed": 9, "track": 10, "source": 16}
    for key, value in changes.items():
        row[indexes[key]] = value
    return row


def snapshot(rows, at=NOW, headers=None):
    return normalize_snapshot({"time": at, "states": rows}, headers or {}, REGION, at, "raw-snapshot")


def trace_row(offset=0, flags=0, **changes):
    row = [offset, 60.0, 24.0, 30000, 300, 90, flags, 0, None, "adsb_icao"]
    indexes = {"lat": 1, "lon": 2, "altitude": 3, "speed": 4, "track": 5, "metadata": 8, "source": 9}
    for key, value in changes.items():
        row[indexes[key]] = value
    return row


def trace(rows, identity="abc123", requested="abc123"):
    payload = {"icao": identity, "timestamp": NOW, "version": "readsb test-fixture", "trace": rows}
    return normalize_trace(payload, requested, [REGION], NOW + 600, "raw-trace")


class NormalizeContractTests(unittest.TestCase):
    def test_trace_rejects_payload_identity_mismatch(self):
        with self.assertRaises(ValueError):
            trace([trace_row()], identity="def456", requested="abc123")

    def test_matching_trace_identity_retains_requested_aircraft(self):
        records, _ = trace([trace_row()], identity="ABC123", requested="abc123")
        self.assertEqual(records[0]["entity_id"], "abc123")

    def test_trace_identifier_format_rejects_malformed_and_preserves_valid_prefix(self):
        for entity in (None, "", "12345", "1234567", "xyz123", "~/abc123", "abc123?", "abc123/"):
            with self.subTest(entity=entity):
                with self.assertRaises(ValueError):
                    trace([trace_row()], identity=None, requested=entity)
        for entity in (" ABC123 ", " ~ABC123 "):
            with self.subTest(entity=entity):
                records, _ = trace([trace_row()], identity=entity, requested=entity)
                self.assertEqual(records[0]["entity_id"], entity.strip().lower())

    def test_trace_provider_version_preserved_without_claiming_pinned_schema(self):
        payload = {"icao": "abc123", "timestamp": NOW, "trace": [trace_row()],
                   "version": "readsb v3.17.9-custom"}
        records, warnings = normalize_trace(payload, "abc123", [REGION], NOW + 600)
        self.assertEqual(records[0]["provider_version"], "readsb v3.17.9-custom")
        self.assertIn("trace_schema_interpretation_not_version_pinned", warnings)
        self.assertNotIn("trace_provider_version_unknown", warnings)
        for version in (None, 123, {}, False):
            with self.subTest(version=version):
                unknown = dict(payload, version=version)
                if version is None:
                    del unknown["version"]
                records, warnings = normalize_trace(unknown, "abc123", [REGION], NOW + 600)
                self.assertIsNone(records[0]["provider_version"])
                self.assertIn("trace_provider_version_unknown", warnings)
                self.assertIn("trace_schema_interpretation_not_version_pinned", warnings)

    def test_stale_refetch_does_not_create_new_measurement_identity(self):
        state = vector()
        fresh, _ = snapshot([state], at=NOW)
        later, _ = snapshot([state], at=NOW + 300)
        self.assertEqual(fresh[0]["observation_id"], later[0]["observation_id"])
        self.assertEqual(fresh[0]["timestamp"], later[0]["timestamp"])
        self.assertEqual(fresh[0]["position_age_s"], 0)
        self.assertEqual(later[0]["position_age_s"], 300)
        self.assertNotIn("stale_position", fresh[0]["quality_flags"])
        self.assertIn("stale_position", later[0]["quality_flags"])

    def test_snapshot_preserves_zero_and_rejects_nonfinite_optional_fields(self):
        records, _ = snapshot([vector(altitude=math.inf, speed=math.nan, track=-math.inf)])
        self.assertIsNone(records[0]["altitude_m"])
        self.assertIsNone(records[0]["groundspeed_mps"])
        self.assertIsNone(records[0]["track_deg"])
        zero, _ = snapshot([vector(altitude=0, speed=0, track=0)])
        self.assertEqual((zero[0]["altitude_m"], zero[0]["groundspeed_mps"], zero[0]["track_deg"]), (0, 0, 0))
        json.dumps(records + zero, allow_nan=False)

    def test_invalid_snapshot_coordinates_supply_no_in_region_position(self):
        for changes in ({"lat": math.nan}, {"lon": math.inf}, {"lat": 91}, {"lon": None}):
            with self.subTest(changes=changes):
                records, _ = snapshot([vector(**changes)])
                self.assertEqual(records, [])

    def test_missing_position_time_remains_unknown_and_flagged(self):
        records, _ = snapshot([vector(timestamp=None)])
        self.assertIsNone(records[0]["timestamp"])
        self.assertIsNone(records[0]["position_age_s"])
        self.assertIn("missing_position_time", records[0]["quality_flags"])

    def test_missing_trace_flags_do_not_invent_age_or_altitude_datum(self):
        for flags in (None, False, True, 0.5):
            with self.subTest(flags=flags):
                records, _ = trace([trace_row(flags=flags)])
                row = records[0]
                self.assertIsNone(row["position_age_s"])
                self.assertIsNone(row["position_stale_flag"])
                self.assertEqual(row["altitude_type"], "unknown")

    def test_trace_source_missing_remains_unknown(self):
        row = trace_row()[:9]
        records, _ = trace([row])
        self.assertEqual(records[0]["position_source"], "unknown")
        self.assertIn("unknown_position_source", records[0]["quality_flags"])

    def test_clear_trace_stale_bit_is_not_zero_age(self):
        records, _ = trace([trace_row(flags=0), trace_row(10, flags=1)])
        self.assertIsNone(records[0]["position_age_s"])
        self.assertIsNone(records[1]["position_age_s"])
        self.assertIs(records[0]["position_stale_flag"], False)
        self.assertIs(records[1]["position_stale_flag"], True)
        self.assertNotIn("trace_stale", records[0]["quality_flags"])
        self.assertIn("trace_stale", records[1]["quality_flags"])
        self.assertIn("unknown_field_age", records[0]["quality_flags"])

    def test_trace_altitude_and_speed_units_and_datum_follow_flags(self):
        records, _ = trace([trace_row(flags=0), trace_row(10, flags=8)])
        self.assertEqual([row["altitude_type"] for row in records], ["barometric", "geometric"])
        self.assertAlmostEqual(records[0]["altitude_m"], 9144.0)
        self.assertAlmostEqual(records[1]["groundspeed_mps"], 154.3332)
        self.assertEqual(records[1]["timestamp"], NOW + 10)

    def test_nonfinite_trace_fields_are_null_not_invented_measurements(self):
        records, _ = trace([trace_row(altitude=math.inf, speed=math.nan, track=True)])
        self.assertIsNone(records[0]["altitude_m"])
        self.assertIsNone(records[0]["groundspeed_mps"])
        self.assertIsNone(records[0]["track_deg"])
        json.dumps(records, allow_nan=False)

    def test_ground_state_is_preserved_and_has_explicit_ground_flag(self):
        snap, _ = snapshot([vector(on_ground=True)])
        track, _ = trace([trace_row(altitude="ground")])
        for row in (snap[0], track[0]):
            with self.subTest(source=row["source_id"]):
                self.assertIs(row["on_ground"], True)
                self.assertIn("on_ground", row["quality_flags"])
        self.assertIsNone(track[0]["altitude_m"])

    def test_fallback_does_not_promote_placeholder_zero_to_adsb(self):
        for headers in ({"X-OpenSky-Auth-Mode-Used": "adsblol-regional"}, {"X-Flight-Source": "adsb.lol"}):
            with self.subTest(headers=headers):
                records, warnings = snapshot([vector(source=0)], headers=headers)
                self.assertEqual(records[0]["position_source"], "unknown")
                self.assertIn("adsb.lol", records[0]["source_id"])
                self.assertIn("upstream_normalized_source_unknown", records[0]["quality_flags"])
                self.assertTrue(warnings)

    def test_known_opensky_source_and_normal_control_do_not_trigger_anomaly(self):
        records = []
        for index in range(8):
            normalized, _ = snapshot([vector(NOW + index * 30, lon=24 + index * 0.08, source=2)], at=NOW + index * 30)
            records.extend(normalized)
        self.assertTrue(all(row["position_source"] == "mlat" for row in records))
        self.assertEqual(screen_aircraft(records, [], {}, NOW, NOW + 300), [])

    def test_input_payloads_are_not_modified(self):
        payload = {"icao": "abc123", "timestamp": NOW, "trace": [trace_row(metadata={"nic": 0})]}
        original = copy.deepcopy(payload)
        normalize_trace(payload, "abc123", [REGION], NOW + 600)
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
