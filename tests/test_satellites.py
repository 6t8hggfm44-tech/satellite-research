"""Offline parser and evidence-semantics tests; fixtures are synthetic.

No fixture is a claim about a real satellite. Checksums are generated for
modified fixed-width fields so range tests cannot pass merely by bad checksum.
"""

import copy
import json
import unittest
from datetime import datetime, timezone

from satresearch.satellites import DEFAULTS, normalize_satellites, screen_satellites


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def checked(line):
    body = line[:68]
    assert len(body) == 68
    return body + str(sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in body) % 10)


def tle(epoch="26010.50000000", inclination=51.0, raan=100.0, mean_motion=15.0):
    line1 = "1 23455U 94089A   97320.90946019  .00000140  00000-0  10191-3 0  2621"
    line2 = "2 23455  99.0090 272.6745 0008546 223.1686 136.8816 14.11711747148495"
    line1 = checked(line1[:18] + epoch + line1[32:])
    line2 = checked(line2[:8] + "{:8.4f}".format(inclination) + " " + "{:8.4f}".format(raan)
                    + line2[25:52] + "{:11.8f}".format(mean_motion) + line2[63:])
    return "0 SYNTHETIC OBJECT\n" + line1 + "\n" + line2 + "\n"


def omm(epoch="2026-01-10T12:00:00Z", **changes):
    result = {
        "NORAD_CAT_ID": 123456, "OBJECT_NAME": "SYNTHETIC OBJECT", "EPOCH": epoch,
        "MEAN_MOTION": 15.0, "INCLINATION": 51.0, "ECCENTRICITY": 0.001,
        "RA_OF_ASC_NODE": 100.0, "ARG_OF_PERICENTER": 20.0, "MEAN_ANOMALY": 30.0,
        "CENTER_NAME": "EARTH", "REF_FRAME": "TEME", "TIME_SYSTEM": "UTC",
        "MEAN_ELEMENT_THEORY": "SGP4",
    }
    result.update(changes)
    return result


def normalized(item=None, snapshot="2026-01-10T13:00:00Z", source="catalog", raw="raw/current.json"):
    records, warnings = normalize_satellites(item if item is not None else omm(), source, snapshot, raw)
    if not records:
        raise AssertionError(warnings)
    return records


class NormalizationTests(unittest.TestCase):
    def test_tle_3le_and_2le_epoch_fields_and_provenance(self):
        text = tle()
        records, warnings = normalize_satellites(text, "catalog", "2026-01-10T13:00:00Z", "raw/tle.txt")
        self.assertEqual(warnings, [])
        record = records[0]
        self.assertEqual(record["entity_id"], "23455")
        self.assertEqual(record["epoch"], utc("2026-01-10T12:00:00Z"))
        self.assertEqual(record["timestamp"], record["epoch"])
        self.assertEqual(record["inclination_deg"], 51.0)
        self.assertEqual(record["mean_motion_rev_day"], 15.0)
        self.assertEqual(record["eccentricity"], 0.0008546)
        self.assertEqual(record["name"], "SYNTHETIC OBJECT")
        two, _ = normalize_satellites("\n".join(text.splitlines()[1:]), "catalog", "2026-01-10T13:00:00Z", "raw/2le.txt")
        self.assertIsNone(two[0]["name"])
        self.assertEqual(two[0]["observation_id"], record["observation_id"])

    def test_checksum_and_line_identity_rejected(self):
        lines = tle().splitlines()
        broken = lines[:]
        broken[1] = broken[1][:-1] + str((int(broken[1][-1]) + 1) % 10)
        records, warnings = normalize_satellites("\n".join(broken), "s", 2000000000, "raw/a")
        self.assertEqual(records, [])
        self.assertIn("checksum mismatch", warnings[0])
        lines[2] = checked(lines[2][:2] + "23456" + lines[2][7:])
        records, warnings = normalize_satellites("\n".join(lines), "s", 2000000000, "raw/a")
        self.assertEqual(records, [])
        self.assertIn("identities disagree", warnings[0])

    def test_tle_ranges_and_epoch_year_pivot(self):
        for text in (tle(inclination=181), tle(mean_motion=0), tle(raan=360), tle(epoch="26366.00000000")):
            with self.subTest(text=text):
                records, warnings = normalize_satellites(text, "s", 4000000000, "raw/a")
                self.assertEqual(records, [])
                self.assertTrue(warnings)
        for token, expected in (("57001.00000000", "1957-01-01T00:00:00Z"),
                                ("56001.00000000", "2056-01-01T00:00:00Z"),
                                ("00000.00000000", "1999-12-31T00:00:00Z"),
                                ("24366.00000000", "2024-12-31T00:00:00Z")):
            records, _ = normalize_satellites(tle(epoch=token), "s", 4000000000, "raw/a")
            self.assertEqual(records[0]["epoch"], utc(expected))

    def test_malformed_pair_does_not_swallow_following_valid_pair(self):
        lines = tle().splitlines()
        payload = lines[1] + "\nBAD NAME\n" + tle()
        records, warnings = normalize_satellites(payload, "s", 2000000000, "raw/a")
        self.assertEqual(len(records), 1)
        self.assertTrue(any("without adjacent" in w for w in warnings))

    def test_unknown_tle_theory_is_not_silently_called_sgp4(self):
        lines = tle().splitlines()
        lines[1] = checked(lines[1][:62] + "2" + lines[1][63:])
        records, warnings = normalize_satellites("\n".join(lines), "s", 2000000000, "raw/a")
        self.assertEqual(records, [])
        self.assertIn("ephemeris type", warnings[0])

    def test_omm_wrappers_numeric_id_and_explicit_metadata(self):
        for payload in (omm(), [omm()], json.dumps([omm()]), {"data": [omm()]}, {"body": json.dumps([omm()])}):
            records, warnings = normalize_satellites(payload, "s", "2026-01-10T13:00:00Z", "raw/a")
            self.assertEqual(warnings, [])
            self.assertEqual(records[0]["entity_id"], "123456")
            self.assertEqual(records[0]["reference_frame"], "TEME")
            self.assertEqual(records[0]["quality_flags"], [])

    def test_omitted_metadata_assumed_and_explicit_incompatibility_rejected(self):
        item = omm(epoch="2026-01-10T12:00:00")
        for field in ("CENTER_NAME", "REF_FRAME", "TIME_SYSTEM", "MEAN_ELEMENT_THEORY"):
            del item[field]
        records, warnings = normalize_satellites(item, "s", "2026-01-10T13:00:00Z", "raw/a")
        self.assertEqual(records[0]["epoch"], utc("2026-01-10T12:00:00Z"))
        self.assertIn("omm_metadata_assumed", records[0]["quality_flags"])
        self.assertEqual(len(records[0]["format_assumptions"]), 4)
        self.assertTrue(warnings)
        for field, value in (("TIME_SYSTEM", "TAI"), ("REF_FRAME", "EME2000"),
                             ("CENTER_NAME", "MARS"), ("MEAN_ELEMENT_THEORY", "OTHER")):
            records, warnings = normalize_satellites(omm(**{field: value}), "s", 2000000000, "raw/a")
            self.assertEqual(records, [])
            self.assertIn("unsupported OMM", warnings[0])

    def test_missing_nonfinite_and_invalid_values_are_not_zero(self):
        for key, value in (("MEAN_MOTION", None), ("MEAN_MOTION", "nan"), ("INCLINATION", True),
                           ("ECCENTRICITY", -0.01), ("ECCENTRICITY", 1), ("MEAN_ANOMALY", 360),
                           ("NORAD_CAT_ID", "A2345"), ("EPOCH", "not-a-date"), ("EPOCH", "2026-01-10")):
            with self.subTest(key=key, value=value):
                records, warnings = normalize_satellites(omm(**{key: value}), "s", 2000000000, "raw/a")
                self.assertEqual(records, [])
                self.assertTrue(warnings)
        records, warnings = normalize_satellites([omm(), omm(MEAN_MOTION=None)], "s", 2000000000, "raw/a")
        self.assertEqual(len(records), 1)
        self.assertEqual(len(warnings), 1)

    def test_invalid_payload_and_naive_snapshot_rejected(self):
        for payload, snapshot in (("{bad", 2000000000), (omm(), "2026-01-10T13:00:00"),
                                  (b"\xff", 2000000000)):
            records, warnings = normalize_satellites(payload, "s", snapshot, "raw/a")
            self.assertEqual(records, [])
            self.assertTrue(warnings)

    def test_duplicates_collapsed_conflicting_epoch_retained_and_flagged(self):
        records, warnings = normalize_satellites([omm(), omm(), omm(MEAN_MOTION=15.3)], "s", 2000000000, "raw/a")
        self.assertEqual(len(records), 2)
        self.assertTrue(any("duplicate" in w for w in warnings))
        self.assertTrue(all("conflicting_elements_same_epoch" in r["quality_flags"] for r in records))
        self.assertEqual(len({r["observation_id"] for r in records}), 2)


class ScreeningTests(unittest.TestCase):
    START = "2026-01-10T00:00:00Z"
    END = "2026-01-11T00:00:00Z"

    def baseline(self, **changes):
        return normalized(omm(epoch="2026-01-09T12:00:00Z", **changes),
                          snapshot="2026-01-09T13:00:00Z", raw="raw/baseline.json")

    def screen(self, records, baseline=None, config=None):
        return screen_satellites(records, baseline or [], config, self.START, self.END)

    def test_ordinary_update_and_raan_wrap_do_not_alert(self):
        self.assertEqual(self.screen(normalized(omm(MEAN_MOTION=15.01, INCLINATION=51.01)), self.baseline()), [])
        self.assertEqual(self.screen(normalized(omm(RA_OF_ASC_NODE=0.2)), self.baseline(RA_OF_ASC_NODE=359.8)), [])
        changed = self.screen(normalized(omm(RA_OF_ASC_NODE=0.2)), self.baseline(RA_OF_ASC_NODE=359.8), {"raan_change_deg": 0.3})
        self.assertEqual(len(changed), 1)
        self.assertAlmostEqual(changed[0]["metrics"]["raan_change_deg"], 0.4)

    def test_deviation_emits_evidence_metrics_and_causal_limits(self):
        events = self.screen(normalized(omm(MEAN_MOTION=15.5, INCLINATION=52)), self.baseline())
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["detector_id"], "satellite_element_discontinuity")
        self.assertEqual(event["domain"], "satellite")
        self.assertEqual(event["priority"], 50)
        self.assertEqual(event["metrics"]["mean_motion_change_rev_day"], 0.5)
        self.assertEqual(event["metrics"]["inclination_change_deg"], 1)
        self.assertEqual(event["metrics"]["epoch_gap_hours"], 24)
        self.assertEqual(event["start"], utc("2026-01-10T13:00:00Z"))
        self.assertEqual(len(event["evidence_ids"]), 2)
        self.assertEqual(event["raw_refs"], ["raw/baseline.json", "raw/current.json"])
        self.assertEqual(event["review_status"], "unreviewed")
        self.assertEqual(event["hypothesis_status"], "not_tested")
        self.assertIn("refitting", " ".join(event["limitations"]))
        self.assertEqual(event["metrics"]["threshold_status"], "experimental_uncalibrated")

    def test_stale_selected_by_retrieval_not_orbit_epoch(self):
        stale = normalized(omm(epoch="2025-12-01T00:00:00Z"))
        events = self.screen(stale)
        self.assertEqual([e["detector_id"] for e in events], ["satellite_catalog_stale"])
        self.assertEqual(events[0]["start"], stale[0]["snapshot_at"])
        self.assertEqual(events[0]["priority"], 20)
        self.assertIn("not a measured position error", " ".join(events[0]["limitations"]))
        self.assertEqual(self.screen(normalized(snapshot="2026-01-09T23:00:00Z")), [])

    def test_no_history_does_not_fabricate_a_deviation(self):
        self.assertEqual(self.screen(normalized(omm(MEAN_MOTION=17))), [])
        other = normalized(omm(epoch="2026-01-09T12:00:00Z", NORAD_CAT_ID=999999), snapshot="2026-01-09T13:00:00Z")
        self.assertEqual(self.screen(normalized(omm(MEAN_MOTION=17)), other), [])
        source_switch = normalized(omm(epoch="2026-01-09T12:00:00Z"), snapshot="2026-01-09T13:00:00Z", source="other")
        self.assertEqual(self.screen(normalized(omm(MEAN_MOTION=17)), source_switch), [])

    def test_baseline_in_window_future_retrieval_or_future_epoch_excluded(self):
        target = normalized(omm(MEAN_MOTION=15.5))
        for baseline in (
            normalized(omm(epoch="2026-01-09T12:00:00Z"), snapshot=self.START),
            normalized(omm(epoch="2026-01-09T12:00:00Z"), snapshot="2026-01-12T00:00:00Z"),
            normalized(omm(epoch="2026-01-11T12:00:00Z"), snapshot="2026-01-09T13:00:00Z"),
        ):
            self.assertEqual(self.screen(target, baseline), [])

    def test_old_history_beyond_configured_gap_excluded(self):
        self.assertEqual(self.screen(normalized(omm(MEAN_MOTION=15.5)), self.baseline(),
                                     {"max_baseline_gap_hours": 12}), [])

    def test_repeated_epoch_and_elements_are_not_an_update(self):
        first = self.baseline()
        same = normalized(omm(epoch="2026-01-09T12:00:00Z"))
        self.assertEqual(self.screen(same, first), [])
        current = normalized(omm(MEAN_MOTION=15.5))
        events = self.screen(current + copy.deepcopy(current), first + copy.deepcopy(first))
        self.assertEqual(len(events), 1)

    def test_same_epoch_conflict_is_not_a_maneuver(self):
        old = self.baseline()
        current = normalized(omm(epoch="2026-01-09T12:00:00Z", MEAN_MOTION=15.5))
        events = self.screen(current, old)
        self.assertEqual([e["detector_id"] for e in events], ["satellite_catalog_conflict"])
        self.assertEqual(events[0]["metrics"]["distinct_element_sets"], 2)
        self.assertEqual(len(events[0]["evidence_ids"]), 2)

    def test_future_epoch_is_quality_event_not_orbital_change(self):
        future = normalized(omm(epoch="2026-01-11T12:00:00Z"))
        self.assertIn("epoch_after_snapshot", future[0]["quality_flags"])
        events = self.screen(future, self.baseline())
        self.assertEqual([e["detector_id"] for e in events], ["satellite_catalog_future_epoch"])

    def test_in_window_predecessors_and_repeat_captures_have_no_lookahead(self):
        first = normalized(omm(epoch="2026-01-10T01:00:00Z"), snapshot="2026-01-10T02:00:00Z", raw="raw/first")
        second = normalized(omm(epoch="2026-01-10T03:00:00Z", MEAN_MOTION=15.5), snapshot="2026-01-10T04:00:00Z", raw="raw/second")
        repeat_first = normalized(omm(epoch="2026-01-10T01:00:00Z"), snapshot="2026-01-10T05:00:00Z", raw="raw/repeat")
        events = self.screen(second + repeat_first + first)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metrics"]["epoch_gap_hours"], 2)
        self.assertEqual(events[0]["start"], utc("2026-01-10T04:00:00Z"))
        self.assertEqual(events[0]["metrics"]["previous_snapshot_at"], utc("2026-01-10T02:00:00Z"))
        # A preceding *epoch* discovered later must not become earlier evidence.
        self.assertEqual(self.screen(second + repeat_first), [])

    def test_historical_epochs_in_same_capture_ordered_without_duplication(self):
        payload = [omm(epoch="2026-01-10T03:00:00Z", MEAN_MOTION=15.5),
                   omm(epoch="2026-01-10T01:00:00Z")]
        events = self.screen(normalized(payload))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metrics"]["epoch_gap_hours"], 2)

    def test_repeated_future_epoch_not_rehabilitated_by_later_capture(self):
        early = normalized(omm(epoch="2026-01-10T03:00:00Z"), snapshot="2026-01-10T02:00:00Z")
        later = normalized(omm(epoch="2026-01-10T03:00:00Z"), snapshot="2026-01-10T04:00:00Z")
        events = self.screen(early + later, self.baseline())
        self.assertEqual([e["detector_id"] for e in events], ["satellite_catalog_future_epoch"])
        self.assertEqual(events[0]["start"], utc("2026-01-10T02:00:00Z"))

    def test_conflict_time_waits_for_both_variants(self):
        first = normalized(snapshot="2026-01-10T13:00:00Z")
        conflict = normalized(omm(MEAN_MOTION=15.5), snapshot="2026-01-10T14:00:00Z")
        events = self.screen(first + conflict)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["start"], utc("2026-01-10T14:00:00Z"))

    def test_deterministic_ids_order_and_no_input_mutation(self):
        baseline = self.baseline()
        current = normalized(omm(MEAN_MOTION=15.5))
        before = copy.deepcopy((current, baseline, DEFAULTS))
        events = self.screen(current, baseline)
        repeated = self.screen(list(reversed(current)), list(reversed(baseline)))
        self.assertEqual(events, repeated)
        self.assertEqual((current, baseline, DEFAULTS), before)
        self.assertNotEqual(events[0]["event_id"], self.screen(current, baseline, {"mean_motion_change_rev_day": 0.2})[0]["event_id"])

    def test_capture_ref_replacement_preserves_observation_identity(self):
        pending = normalized(raw="pending-capture")
        captured = normalized(raw="capture-001")
        self.assertEqual(pending[0]["observation_id"], captured[0]["observation_id"])
        pending[0]["raw_ref"] = "capture-001"
        pending[0]["raw_refs"] = ["capture-001"]
        self.assertEqual(pending, captured)

    def test_threshold_validation_and_endpoint_inclusion(self):
        for config in ({"max_epoch_age_hours": -1}, {"raan_change_deg": float("nan")}, {"typo": 1}):
            with self.assertRaises(ValueError):
                self.screen([], config=config)
        with self.assertRaises(ValueError):
            screen_satellites([], [], None, self.END, self.START)
        at_end = normalized(omm(epoch="2025-12-01T00:00:00Z"), snapshot=self.END)
        self.assertEqual(len(self.screen(at_end)), 1)


if __name__ == "__main__":
    unittest.main()
