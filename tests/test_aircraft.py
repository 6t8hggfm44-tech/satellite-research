"""Adversarial synthetic data tests; none is an operational calibration."""

import copy
import json
import math
import random
import unittest

from satresearch.aircraft import DEFAULTS, screen_aircraft


START = 1710000000.0


def observation(index, offset=None, **changes):
    row = {
        "observation_id": "o-" + str(index), "entity_id": "abc123",
        "timestamp": START + (index * 30 if offset is None else offset),
        "lat": 60.0, "lon": 24.0 + index * 0.05,
        "altitude_m": 9000.0, "altitude_type": "barometric",
        "groundspeed_mps": 230.0, "track_deg": 90.0,
        "position_source": "adsb_icao", "region": "test-region",
        "source_id": "publisher-a", "snapshot_at": START + 10000,
        "position_age_s": 0.0, "quality_flags": [],
        "raw_ref": "captures/input.json",
    }
    row.update(changes)
    return row


def screen(rows, baseline=(), config=None, end=START + 1000):
    return screen_aircraft(rows, baseline, config or {}, START, end)


def selected(events, detector):
    return [event for event in events if event["detector_id"] == "aircraft." + detector]


def baseline_rows():
    return [observation(day * 10 + index, -day * 86400 + index * 60,
                        observation_id="b-{}-{}".format(day, index),
                        groundspeed_mps=200.0 + index % 3,
                        raw_ref="captures/day-{}.json".format(day))
            for day in (1, 2, 3) for index in range(10)]


class AircraftScreenTests(unittest.TestCase):
    def test_no_data_and_ordinary_control_do_not_force_candidates(self):
        self.assertEqual(screen([]), [])
        self.assertEqual(screen([None, {}, {"timestamp": math.nan}]), [])
        self.assertEqual(screen([observation(i) for i in range(10)]), [])

    def test_coordinate_jump_has_exact_evidence_and_unreviewed_status(self):
        rows = [observation(0, lon=20), observation(1, lon=25)]
        event = selected(screen(rows), "coordinate_jump")[0]
        self.assertEqual(event["evidence_ids"], ["o-0", "o-1"])
        self.assertEqual(event["raw_refs"], ["captures/input.json"])
        self.assertEqual(event["metrics"]["observation_count"], 2)
        self.assertEqual(event["metrics"]["evidence_count"], 2)
        self.assertGreater(event["metrics"]["max_implied_speed_mps"], 9000)
        self.assertEqual(event["review_status"], "unreviewed")
        self.assertEqual(event["hypothesis_status"], "not_tested")
        self.assertTrue(all(field in event for field in ("event_id", "domain", "detector_version", "entity_id", "region", "start", "end", "priority", "summary", "limitations")))
        json.dumps(event, allow_nan=False)

    def test_source_switch_is_qualified_and_lower_priority(self):
        rows = [observation(0, lon=20), observation(1, lon=25)]
        same = selected(screen(rows), "coordinate_jump")[0]
        rows[1]["position_source"] = "mlat"
        switched = selected(screen(rows), "coordinate_jump")[0]
        self.assertEqual(switched["metrics"]["source_switch_count"], 1)
        self.assertLess(switched["priority"], same["priority"])
        self.assertTrue(any("source or publisher change" in value for value in switched["limitations"]))

    def test_publisher_switch_is_not_independent_motion(self):
        event = selected(screen([observation(0, lon=20), observation(1, lon=25, source_id="publisher-b")]), "coordinate_jump")[0]
        self.assertEqual(event["metrics"]["publisher_switch_count"], 1)
        self.assertEqual(event["priority"], 45)

    def test_gaps_and_too_short_pairs_do_not_create_jumps(self):
        for interval in (0.1, 121, 600):
            with self.subTest(interval=interval):
                self.assertEqual(screen([observation(0, lon=20), observation(1, interval, lon=25)]), [])

    def test_stale_invalid_and_future_flags_block_pairs(self):
        for flag in ("stale_position", "trace_stale", "stale_feed", "invalid_position", "future_position", "missing_position_time"):
            with self.subTest(flag=flag):
                self.assertEqual(screen([observation(0, lon=20), observation(1, lon=25, quality_flags=[flag])]), [])
        for age in (31, -1, math.nan):
            with self.subTest(age=age):
                self.assertEqual(screen([observation(0, lon=20), observation(1, lon=25, position_age_s=age)]), [])

    def test_unknown_age_jump_carries_freshness_limitation(self):
        rows = [observation(0, lon=20), observation(1, lon=25, position_age_s=None)]
        event = selected(screen(rows), "coordinate_jump")[0]
        self.assertEqual(event["metrics"]["unknown_position_age_count"], 1)
        self.assertTrue(any("freshness has not been established" in value for value in event["limitations"]))

    def test_invalid_or_missing_middle_position_is_an_adjacency_barrier(self):
        for changes in ({"lat": None}, {"lon": 200}, {"lat": math.inf}, {"quality_flags": ["stale_position"]}):
            rows = [observation(0, lon=20), observation(1, **changes), observation(2, lon=25)]
            with self.subTest(changes=changes):
                self.assertEqual(selected(screen(rows), "coordinate_jump"), [])

    def test_dateline_is_not_a_360_degree_jump(self):
        self.assertEqual(screen([observation(0, lat=0, lon=179.999), observation(1, lat=0, lon=-179.999)]), [])

    def test_frozen_positions_need_duration_distinct_times_and_moving_speed(self):
        rows = [observation(i, i * 60, lon=24, groundspeed_mps=150) for i in range(4)]
        event = selected(screen(rows), "frozen_position")[0]
        self.assertEqual(event["metrics"]["span_s"], 180)
        self.assertEqual(event["metrics"]["observation_count"], 4)
        self.assertEqual(selected(screen(rows[:3]), "frozen_position"), [])
        for row in rows:
            row["groundspeed_mps"] = 0
        self.assertEqual(selected(screen(rows), "frozen_position"), [])

    def test_repeated_poll_of_one_timestamp_does_not_establish_persistence(self):
        rows = [observation(i, 0, lon=24) for i in range(20)]
        self.assertEqual(screen(rows), [])

    def test_equivalent_duplicates_preserve_ids_without_inflating_points(self):
        rows = [observation(i, i * 60, lon=24) for i in range(4)]
        rows.extend(copy.deepcopy(rows))
        other_id = copy.deepcopy(rows[1])
        other_id["observation_id"] = "same-time-another-id"
        other_id["raw_ref"] = "captures/duplicate.json"
        rows.append(other_id)
        event = selected(screen(rows), "frozen_position")[0]
        self.assertEqual(event["metrics"]["observation_count"], 4)
        self.assertEqual(event["metrics"]["evidence_count"], 5)
        self.assertEqual(len(event["evidence_ids"]), len(set(event["evidence_ids"])))
        self.assertEqual(event["raw_refs"], ["captures/duplicate.json", "captures/input.json"])

    def test_conflicting_duplicate_times_and_ids_are_barriers(self):
        rows = [observation(0, lon=20), observation(1, lon=22), observation(2, 30, lon=28), observation(3, 60, lon=25)]
        self.assertEqual(selected(screen(rows), "coordinate_jump"), [])
        frozen = [observation(i, i * 60, lon=24, observation_id="reused") for i in range(4)]
        self.assertEqual(screen(frozen), [])

    def test_unknown_age_requires_explicit_clear_serializer_flag_for_persistence(self):
        rows = [observation(i, i * 60, lon=24, position_age_s=None) for i in range(4)]
        self.assertEqual(selected(screen(rows), "frozen_position"), [])
        for row in rows:
            row["position_stale_flag"] = False
        event = selected(screen(rows), "frozen_position")[0]
        self.assertEqual(event["metrics"]["serializer_unflagged_unknown_age_count"], 4)
        self.assertTrue(any("unknown, not zero" in limit for limit in event["limitations"]))
        self.assertTrue(all(row["position_age_s"] is None for row in rows))
        rows[1]["position_stale_flag"] = True
        self.assertEqual(selected(screen(rows), "frozen_position"), [])

    def test_clear_serializer_flag_does_not_override_known_old_age(self):
        rows = [observation(i, i * 60, lon=24, position_stale_flag=False, position_age_s=999) for i in range(4)]
        self.assertEqual(screen(rows), [])

    def test_persistence_stops_at_source_unknown_source_gap_or_invalid(self):
        original = [observation(i, i * 60, lon=24) for i in range(4)]
        for changes in ({"position_source": "mlat"}, {"position_source": "unknown"}, {"source_id": "publisher-b"}, {"quality_flags": ["invalid_position"]}):
            rows = copy.deepcopy(original)
            rows[2].update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(selected(screen(rows), "frozen_position"), [])
        rows = [observation(i, i * 300, lon=24) for i in range(4)]
        self.assertEqual(screen(rows), [])

    def test_slow_aloft_requires_present_altitude_speed_and_duration(self):
        original = [observation(i, i * 60, groundspeed_mps=20) for i in range(4)]
        event = selected(screen(original), "low_speed_aloft")[0]
        self.assertEqual(event["metrics"]["median_reported_speed_mps"], 20)
        for changes in ({"altitude_m": None}, {"groundspeed_mps": None}, {"altitude_m": 500}, {"quality_flags": ["on_ground"]}):
            rows = [dict(row, **changes) for row in original]
            with self.subTest(changes=changes):
                self.assertEqual(selected(screen(rows), "low_speed_aloft"), [])
        self.assertEqual(selected(screen(original[:3]), "low_speed_aloft"), [])

    def test_normal_observation_breaks_slow_candidate_group(self):
        rows = [observation(i, i * 60, groundspeed_mps=20) for i in range(7)]
        rows[3]["groundspeed_mps"] = 230
        self.assertEqual(selected(screen(rows), "low_speed_aloft"), [])

    def test_explicit_on_ground_blocks_persistence_without_quality_flag(self):
        for speed in (20, 230):
            rows = [observation(i, i * 60, lon=24, groundspeed_mps=speed,
                                on_ground=True, quality_flags=[]) for i in range(4)]
            with self.subTest(speed=speed):
                self.assertEqual(screen(rows), [])

    def test_group_adjacent_jumps_and_split_at_normal_pair(self):
        connected = [observation(i, lon=20 + i * 2) for i in range(3)]
        events = selected(screen(connected), "coordinate_jump")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metrics"]["pair_count"], 2)
        self.assertEqual(events[0]["evidence_ids"], ["o-0", "o-1", "o-2"])
        separated = [observation(0, lon=20), observation(1, lon=22), observation(2, lon=22.01), observation(3, lon=24)]
        self.assertEqual(len(selected(screen(separated), "coordinate_jump")), 2)

    def test_baseline_outlier_has_adequate_days_and_exact_baseline_evidence(self):
        controls = baseline_rows()
        event = selected(screen([observation(0, groundspeed_mps=400)], controls), "baseline_speed_outlier")[0]
        self.assertEqual(event["metrics"]["baseline_samples_min"], 30)
        self.assertEqual(event["metrics"]["baseline_distinct_days_min"], 3)
        self.assertEqual(event["metrics"]["evidence_count"], 31)
        self.assertEqual(event["evidence_ids"], sorted(["o-0"] + [row["observation_id"] for row in controls]))
        self.assertEqual(selected(screen([observation(0, groundspeed_mps=201)], controls), "baseline_speed_outlier"), [])

    def test_inadequate_or_incomparable_baseline_produces_no_outlier(self):
        current = [observation(0, groundspeed_mps=400)]
        controls = baseline_rows()
        variants = [controls[:29], controls[:10] * 3,
                    [dict(row, entity_id="other") for row in controls],
                    [dict(row, region="other") for row in controls],
                    [dict(row, altitude_m=1000) for row in controls],
                    [dict(row, altitude_type="geometric") for row in controls],
                    [dict(row, altitude_type="unknown") for row in controls],
                    [dict(row, position_source="mlat") for row in controls],
                    [dict(row, position_age_s=None) for row in controls]]
        for index, baseline in enumerate(variants):
            with self.subTest(variant=index):
                self.assertEqual(selected(screen(current, baseline), "baseline_speed_outlier"), [])
        one_day = [dict(row, timestamp=START - 86400 + index * 10) for index, row in enumerate(controls)]
        self.assertEqual(selected(screen(current, one_day), "baseline_speed_outlier"), [])

    def test_baseline_leakage_including_reused_id_cannot_change_results(self):
        current = [observation(0, groundspeed_mps=400)]
        controls = baseline_rows()
        expected = screen(current, controls)
        future = [dict(row, timestamp=START + index * 10, groundspeed_mps=400) for index, row in enumerate(controls)]
        self.assertEqual(screen(current, controls + future), expected)
        self.assertEqual(selected(screen(current, future), "baseline_speed_outlier"), [])
        old = [dict(row, timestamp=row["timestamp"] - 40 * 86400) for row in controls]
        self.assertEqual(selected(screen(current, old), "baseline_speed_outlier"), [])

    def test_baseline_candidates_group_only_consecutive_outliers(self):
        rows = [observation(i, groundspeed_mps=400) for i in range(4)]
        events = selected(screen(rows, baseline_rows()), "baseline_speed_outlier")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metrics"]["observation_count"], 4)
        self.assertEqual(events[0]["metrics"]["evidence_count"], 34)
        rows[2]["groundspeed_mps"] = 200
        self.assertEqual(len(selected(screen(rows, baseline_rows()), "baseline_speed_outlier")), 2)

    def test_input_permutation_is_stable_and_records_are_immutable(self):
        rows = [observation(i, lon=20 + i * 2) for i in range(4)]
        controls = baseline_rows()
        before = copy.deepcopy((rows, controls, DEFAULTS))
        expected = screen(rows, controls)
        rng = random.Random(9)
        for _ in range(5):
            shuffled = rows[:]
            rng.shuffle(shuffled)
            self.assertEqual(screen(shuffled, list(reversed(controls))), expected)
        self.assertEqual((rows, controls, DEFAULTS), before)

    def test_window_limits_do_not_pair_across_the_event_boundary(self):
        rows = [observation(0, -10, lon=20), observation(1, 10, lon=25)]
        self.assertEqual(selected(screen(rows), "coordinate_jump"), [])
        self.assertEqual(selected(screen([observation(0, lon=20), observation(1, 30, lon=25)], end=START + 30), "coordinate_jump")[0]["end"], START + 30)

    def test_bad_windows_and_settings_fail_explicitly(self):
        for start, end in ((math.nan, START), (START + 1, START), (START, math.inf)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                screen_aircraft([], [], {}, start, end)
        for config in ({"jump_speed_mps": -1}, {"baseline_min_days": 1.5}, {"max_gap_s": 0.5}, {"frozen_min_points": True}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                screen([], config=config)


if __name__ == "__main__":
    unittest.main()
