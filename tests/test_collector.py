"""Acquisition contract tests using mock transports and real temporary Stores.

No test connects to GEV, contacts a publisher, starts Pinokio or sleeps. Raw
capture assertions inspect preserved bytes, not just mocked call counts.
"""

import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from satresearch import collector
from satresearch.storage import Store


NOW = datetime(2026, 2, 10, 12, tzinfo=timezone.utc).timestamp()
BASE = "http://127.0.0.1:43210"


def state_vector(timestamp=NOW - 10):
    return ["abc123", "SYNTHETIC", "", timestamp, NOW, 0.5, 0.5,
            1000, False, 100, 90, 0, None, 1100, "", False, 0]


def response(payload=None, status="available", http_status=200, headers=None, body=None, **extras):
    if body is None:
        body = json.dumps({"time": NOW, "states": []} if payload is None else payload).encode()
    meta = {"retrieved_at": NOW, "status": status, "headers": headers or {},
            "url": BASE + "/api/mock", "request": {"method": "GET"}}
    if http_status is not None:
        meta["http_status"] = http_status
    meta.update(extras)
    return body, meta


def satellite_payload():
    return [{"NORAD_CAT_ID": 123456, "OBJECT_NAME": "SYNTHETIC",
             "EPOCH": datetime.fromtimestamp(NOW - 60, timezone.utc).isoformat(),
             "MEAN_MOTION": 15, "INCLINATION": 51, "ECCENTRICITY": 0.001,
             "RA_OF_ASC_NODE": 100, "ARG_OF_PERICENTER": 20, "MEAN_ANOMALY": 30,
             "CENTER_NAME": "EARTH", "REF_FRAME": "TEME", "TIME_SYSTEM": "UTC",
             "MEAN_ELEMENT_THEORY": "SGP4"}]


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data_dir = Path(self.temporary.name)
        self.config = collector.load_config()
        self.config.update({
            "regions": [{"id": "synthetic", "lat": 0, "lon": 0, "bbox": [-2, -2, 2, 2]}],
            "satellite_groups": [], "traces_per_region": 0, "minimum_free_bytes": 0,
        })

    def collect(self, fake_response, now=NOW, force=False):
        with patch.object(collector, "discover_gev", return_value=BASE), \
                patch.object(collector, "fetch", return_value=fake_response) as transport, \
                patch.object(collector.time, "time", return_value=now):
            result = collector.collect(self.data_dir, self.config, force=force)
        return result, transport

    def captures(self):
        with Store(self.data_dir) as store:
            return store.captures(None, None)

    def observations(self, domain="aircraft"):
        with Store(self.data_dir) as store:
            return store.observations(domain, None, None)

    def test_runtime_not_ready_reports_unavailable_and_never_fetches(self):
        self.config["pterm_command"] = ["synthetic-pterm"]
        result = SimpleNamespace(returncode=0, stdout=json.dumps({"ready": False, "source": {"local": True}}))
        with patch.object(collector.subprocess, "run", return_value=result), \
                patch.object(collector, "fetch") as transport, \
                patch.object(collector.time, "time", return_value=NOW):
            report = collector.collect(self.data_dir, self.config)
        self.assertEqual(report["status"], "runtime_unavailable")
        self.assertEqual(report["requests"], [])
        transport.assert_not_called()
        saved = json.loads((self.data_dir / "health.json").read_text())
        self.assertEqual(saved["status"], "runtime_unavailable")
        self.assertFalse((self.data_dir / "store.sqlite3").exists())

    def test_discovery_failure_is_reported_without_empty_healthy_capture(self):
        with patch.object(collector, "discover_gev", side_effect=RuntimeError("synthetic runtime unavailable")), \
                patch.object(collector, "fetch") as transport:
            report = collector.collect(self.data_dir, self.config)
        self.assertEqual(report["status"], "runtime_unavailable")
        self.assertIn("synthetic runtime", report["error"])
        transport.assert_not_called()

    def test_timeout_capture_preserved_and_regular_retry_cadence_persisted(self):
        failed = response(status="request_failed", http_status=None, body=b"", error="TimeoutError: synthetic timeout")
        report, transport = self.collect(failed)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(transport.call_count, 1)
        captures = self.captures()
        self.assertEqual(len(captures), 1)
        self.assertIn("TimeoutError", captures[0]["error"])
        self.assertNotIn("http_status", captures[0])
        with Store(self.data_dir) as store:
            self.assertEqual(store.read_capture(captures[0]["capture_id"]), b"")
            self.assertEqual(store.stats()["observations"], 0)
        saved = collector.read_json(self.data_dir / "collector-state.json")
        self.assertEqual(saved["sources"]["aircraft:synthetic"]["next_due"], NOW + self.config["aircraft_interval_s"])
        second, transport = self.collect(response(), now=NOW + 1)
        self.assertEqual(second["requests"], [])
        transport.assert_not_called()

    def test_403_error_body_and_cooldown_survive_force(self):
        body = b"synthetic provider access refusal"
        report, _ = self.collect(response(status="request_failed", http_status=403, body=body))
        capture_id = report["requests"][0]["capture_id"]
        with Store(self.data_dir) as store:
            self.assertEqual(store.read_capture(capture_id), body)
        state = collector.read_json(self.data_dir / "collector-state.json")["sources"]["aircraft:synthetic"]
        self.assertGreater(state["retry_after"], NOW)
        second, transport = self.collect(response(), now=NOW + 60, force=True)
        self.assertEqual(second["requests"], [])
        transport.assert_not_called()

    def test_retry_after_seconds_and_http_date_both_enforce_cooldown(self):
        for retry_after in ("1200", formatdate(NOW + 1200, usegmt=True)):
            with self.subTest(retry_after=retry_after), tempfile.TemporaryDirectory() as directory:
                self.data_dir = Path(directory)
                self.collect(response(status="request_failed", http_status=429,
                                      headers={"retry-after": retry_after}, body=b"synthetic rate limit"))
                state = collector.read_json(self.data_dir / "collector-state.json")["sources"]["aircraft:synthetic"]
                self.assertEqual(state["retry_after"], NOW + 1200)
                _, transport = self.collect(response(), now=NOW + 1199, force=True)
                transport.assert_not_called()
                _, transport = self.collect(response(), now=NOW + 1200, force=True)
                self.assertEqual(transport.call_count, 1)

    def test_default_cadence_skips_network_until_each_source_due(self):
        self.config["satellite_groups"] = ["stations"]

        def deliver(url, config):
            return response(satellite_payload() if "/celestrak/" in url else None,
                            retrieved_at=collector.time.time())

        with patch.object(collector, "discover_gev", return_value=BASE), \
                patch.object(collector, "fetch", side_effect=deliver) as transport:
            with patch.object(collector.time, "time", return_value=NOW):
                first = collector.collect(self.data_dir, self.config)
            self.assertEqual(len(first["requests"]), 2)
            with patch.object(collector.time, "time", return_value=NOW + 1):
                second = collector.collect(self.data_dir, self.config)
            self.assertEqual(second["requests"], [])
            self.assertEqual(transport.call_count, 2)
            with patch.object(collector.time, "time", return_value=NOW + self.config["aircraft_interval_s"]):
                third = collector.collect(self.data_dir, self.config)
            self.assertEqual([r["source"] for r in third["requests"]], ["aircraft:synthetic"])
            self.assertEqual(transport.call_count, 3)
            with patch.object(collector.time, "time", return_value=NOW + self.config["aircraft_interval_s"] + 1):
                fourth = collector.collect(self.data_dir, self.config)
            self.assertEqual(fourth["requests"], [])
            self.assertEqual(transport.call_count, 3)

    def test_partial_vector_parse_retains_valid_only_and_preserves_full_response(self):
        payload = {"time": NOW, "states": [state_vector(), ["too-short"], state_vector(None)]}
        body, meta = response(payload)
        report, _ = self.collect((body, meta))
        request = report["requests"][0]
        self.assertEqual(request["records"], 1)
        self.assertTrue(any("malformed" in w for w in request["warnings"]))
        self.assertTrue(any("missing event timestamp" in w for w in request["warnings"]))
        self.assertEqual(len(self.observations()), 1)
        with Store(self.data_dir) as store:
            self.assertEqual(store.read_capture(request["capture_id"]), body)

    def test_parse_error_empty_and_truncated_have_no_phantom_observations(self):
        attempts = [
            (response(body=b"{broken JSON"), "parse_failed"),
            (response({"states": "invalid"}), "parse_failed"),
            (response({"time": NOW, "states": None}), "empty_response"),
            (response({"time": NOW, "states": [state_vector(None)]}), "empty_response"),
            (response({"time": NOW, "states": [state_vector()]}, status="truncated"), "truncated"),
        ]
        for returned, expected in attempts:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                self.data_dir = Path(directory)
                report, _ = self.collect(returned)
                self.assertEqual(report["requests"][0]["status"], expected)
                self.assertEqual(self.observations(), [])
                capture = self.captures()[0]
                self.assertEqual(capture["normalized_count"], 0)
                self.assertEqual(capture["coverage"]["first_event"], None)
                self.assertFalse(capture["coverage"]["continuous"])

    def test_satellite_placeholder_is_replaced_by_real_capture_reference(self):
        self.config.update(regions=[], satellite_groups=["stations"])
        body, meta = response(satellite_payload())
        report, _ = self.collect((body, meta))
        self.assertEqual(report["requests"][0]["records"], 1)
        records = self.observations("satellite")
        self.assertEqual(len(records), 1)
        capture_id = report["requests"][0]["capture_id"]
        self.assertEqual(records[0]["raw_ref"], capture_id)
        self.assertEqual(records[0]["raw_refs"], [capture_id])
        self.assertNotIn("pending-capture", json.dumps(records))
        with Store(self.data_dir) as store:
            self.assertEqual(store.read_capture(capture_id), body)
            self.assertTrue(store.verify()["ok"])

    def test_all_collection_requests_use_fixed_loopback_routes(self):
        self.config.update(traces_per_region=1, satellite_groups=["stations"])

        def deliver(url, config):
            path = urllib.parse.urlsplit(url).path
            if path == "/api/opensky":
                return response({"time": NOW, "states": [state_vector()]})
            if path == "/api/adsblol/trace":
                return response({"timestamp": NOW - 30, "trace": [[0, 0.5, 0.5, 5000, 200, 90, 0, 0, {}, "adsb_icao"]]})
            if path == "/api/celestrak/stations":
                return response(satellite_payload())
            raise AssertionError("unexpected endpoint: " + path)

        with patch.object(collector, "discover_gev", return_value=BASE), \
                patch.object(collector, "fetch", side_effect=deliver) as transport, \
                patch.object(collector.time, "time", return_value=NOW):
            report = collector.collect(self.data_dir, self.config)
        self.assertEqual(len(report["requests"]), 3)
        urls = [call.args[0] for call in transport.call_args_list]
        self.assertEqual({urllib.parse.urlsplit(url).path for url in urls},
                         {"/api/opensky", "/api/adsblol/trace", "/api/celestrak/stations"})
        for url in urls:
            parsed = urllib.parse.urlsplit(url)
            self.assertEqual(parsed.hostname, "127.0.0.1")
            self.assertIsNone(parsed.username)
            self.assertIsNone(parsed.password)


class TransportBoundaryTests(unittest.TestCase):
    def test_local_base_rejects_remote_credentials_and_nonbase_components(self):
        invalid = ("https://example.invalid", "http://127.0.0.1.example.invalid", "file:///tmp/example",
                   "http://synthetic@localhost:43210", "http://synthetic:synthetic@localhost:43210",
                   BASE + "/api/opensky", BASE + "?token=synthetic", BASE + "#fragment")
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                collector.local_base(url)
        for url in (BASE, "http://localhost:43210/", "http://[::1]:43210"):
            self.assertEqual(collector.local_base(url), url.rstrip("/"))

    def test_explicit_remote_runtime_url_never_triggers_fetch(self):
        config = collector.load_config()
        config.update(gev_base_url="https://example.invalid", minimum_free_bytes=0)
        with tempfile.TemporaryDirectory() as directory, patch.object(collector, "fetch") as transport:
            report = collector.collect(directory, config)
        self.assertEqual(report["status"], "runtime_unavailable")
        transport.assert_not_called()

    def test_discovered_nonlocal_runtime_is_rejected(self):
        config = {"pterm_command": ["synthetic-pterm"]}
        for local, url in ((False, BASE), (True, "https://example.invalid")):
            payload = {"ready": True, "ready_url": url, "source": {"local": local}}
            with self.subTest(local=local, url=url), \
                    patch.object(collector.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))), \
                    self.assertRaises((ValueError, RuntimeError)):
                collector.discover_gev(config)

    def test_redirects_are_rejected_even_when_destination_is_local(self):
        handler = collector.NoRedirect()
        request = urllib.request.Request(BASE + "/api/opensky")
        for target in ("https://example.invalid/api", BASE + "/other"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, target)

    def test_fetch_timeout_and_http_error_preserve_distinct_outcomes(self):
        config = {"request_timeout_s": 1, "max_response_bytes": 4096}
        opener = MagicMock()
        opener.open.side_effect = TimeoutError("synthetic timeout")
        with patch.object(collector.urllib.request, "build_opener", return_value=opener), \
                patch.object(collector.time, "time", return_value=NOW):
            body, meta = collector.fetch(BASE + "/api/opensky", config)
        self.assertEqual(body, b"")
        self.assertEqual(meta["status"], "request_failed")
        self.assertNotIn("http_status", meta)
        self.assertIn("TimeoutError", meta["error"])

        error_body = b"synthetic rate-limit reply"
        opener.open.side_effect = urllib.error.HTTPError(BASE + "/api/opensky", 429, "Too Many Requests",
                                                        {"Retry-After": "600", "Content-Type": "text/plain"}, io.BytesIO(error_body))
        with patch.object(collector.urllib.request, "build_opener", return_value=opener):
            body, meta = collector.fetch(BASE + "/api/opensky", config)
        self.assertEqual(body, error_body)
        self.assertEqual(meta["http_status"], 429)
        self.assertEqual(meta["headers"]["retry-after"], "600")
        self.assertEqual(meta["status"], "request_failed")

    def test_fetch_disables_environment_proxy_and_installs_no_redirect_handler(self):
        opener = MagicMock()
        opener.open.side_effect = TimeoutError("synthetic")
        with patch.object(collector.urllib.request, "build_opener", return_value=opener) as builder:
            collector.fetch(BASE + "/api/celestrak/stations", {"request_timeout_s": 1, "max_response_bytes": 4096})
        handlers = builder.call_args.args
        proxy = next(h for h in handlers if isinstance(h, urllib.request.ProxyHandler))
        self.assertEqual(proxy.proxies, {})
        self.assertTrue(any(isinstance(h, collector.NoRedirect) for h in handlers))

    def test_fetch_byte_cap_marks_saved_prefix_truncated(self):
        received = MagicMock()
        received.__enter__.return_value = received
        received.code = 200
        received.headers = {"Content-Type": "application/json"}
        received.read.return_value = b"123456789"
        opener = MagicMock()
        opener.open.return_value = received
        with patch.object(collector.urllib.request, "build_opener", return_value=opener):
            body, meta = collector.fetch(BASE + "/api/opensky", {"request_timeout_s": 1, "max_response_bytes": 8})
        received.read.assert_called_once_with(9)
        self.assertEqual(body, b"12345678")
        self.assertEqual(meta["status"], "truncated")
        self.assertEqual(meta["http_status"], 200)
        self.assertIn("saved prefix only", meta["error"])


if __name__ == "__main__":
    unittest.main()
