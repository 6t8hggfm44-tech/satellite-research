"""Offline service-installer tests: only temporary paths and simulated launchctl."""

from contextlib import contextmanager, redirect_stdout
import copy
import fcntl
import io
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import install_collector_service as installer


class SimulatedLaunchctl:
    def __init__(self, spec, loaded=False, output=None, bootstrap_error=False):
        self.loaded = loaded
        self.output = output if output is not None else "\n".join([
            spec["WorkingDirectory"], spec["ProgramArguments"][4],
            spec["ProgramArguments"][6]])
        self.bootstrap_error = bootstrap_error
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == "print":
            return subprocess.CompletedProcess(args, 0 if self.loaded else 1,
                                               self.output if self.loaded else "", "")
        if args[0] == "enable":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "bootstrap":
            if self.bootstrap_error:
                return subprocess.CompletedProcess(args, 5, "", "synthetic registration failure")
            self.loaded = True
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError("Unexpected service-control operation: " + repr(args))


class ServiceInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / "checkout"
        (self.checkout / "satresearch").mkdir(parents=True)
        (self.checkout / "satresearch/__main__.py").write_text("# synthetic checkout\n")
        self.config = self.checkout / "config.json"
        self.config.write_text("{}\n")
        self.data = self.root / "data"
        self.data.mkdir()
        self.home = self.root / "fake-home"
        self.home.mkdir()
        self.source = self.root / "prepared.plist"
        self.destination = self.home / "Library/LaunchAgents" / (installer.LABEL + ".plist")
        self.spec = {
            "Label": installer.LABEL,
            "ProgramArguments": [str(Path(sys.executable).resolve()), "-m", "satresearch",
                                 "--data-dir", str(self.data), "--config", str(self.config), "service"],
            "WorkingDirectory": str(self.checkout), "RunAtLoad": True, "KeepAlive": True,
            "ThrottleInterval": 60, "ProcessType": "Background", "LowPriorityIO": True,
            "StandardOutPath": str(self.data / "service.stdout.log"),
            "StandardErrorPath": str(self.data / "service.stderr.log"),
        }
        self.save_spec(self.spec)
        # A missed mock must fail rather than touch a real process or service.
        self.subprocess_guard = patch.object(installer.subprocess, "run", side_effect=AssertionError("No real subprocesses"))
        self.subprocess_guard.start()
        self.addCleanup(self.subprocess_guard.stop)
        self.kill_guard = patch.object(installer.os, "kill", side_effect=AssertionError("No process termination"))
        self.kill_guard.start()
        self.addCleanup(self.kill_guard.stop)

    def save_spec(self, spec):
        self.source.write_bytes(plistlib.dumps(spec))

    def install(self, fake):
        with patch.object(installer, "launchctl", side_effect=fake), patch.object(installer.sys, "platform", "darwin"):
            return installer.install(self.source, home=self.home, uid=501)

    def status(self, **changes):
        value = {"pid": 12345, "updated_at": 990, "status": "running", "last_cycle_status": "completed"}
        value.update(changes)
        (self.data / "service-status.json").write_text(json.dumps(value))

    @contextmanager
    def held_lock(self):
        path = self.data / "collector.lock"
        path.write_text("synthetic existing collector\n")
        with path.open("r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield path
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def test_validate_expected_definition_and_guard_paths(self):
        self.assertEqual(installer.validate(self.source), self.spec)
        variants = []
        for field, value in [("Label", "other.label"), ("KeepAlive", False), ("RunAtLoad", False),
                             ("ThrottleInterval", 1), ("ProcessType", "Interactive"),
                             ("LowPriorityIO", False), ("StandardOutPath", str(self.root / "wrong.log")),
                             ("StandardErrorPath", str(self.root / "wrong.log")),
                             ("WorkingDirectory", "relative"), ("ProgramArguments", 123)]:
            item = copy.deepcopy(self.spec)
            item[field] = value
            variants.append((field, item))
        for index, value in [(0, str(self.root / "missing-python")), (4, "relative-data"),
                             (6, str(self.root / "missing-config")), (7, "collect")]:
            item = copy.deepcopy(self.spec)
            item["ProgramArguments"][index] = value
            variants.append(("argument-%d" % index, item))
        item = copy.deepcopy(self.spec)
        item["UserName"] = "unexpected"
        variants.append(("extra-key", item))
        for label, spec in variants:
            with self.subTest(label=label):
                self.save_spec(spec)
                with self.assertRaises(ValueError):
                    installer.validate(self.source)

    def test_check_only_has_no_writes_or_service_calls(self):
        before = self.snapshot()
        output = io.StringIO()
        with patch.object(installer, "launchctl", side_effect=AssertionError("No service calls")), redirect_stdout(output):
            self.assertEqual(installer.main([str(self.source), "--check-only"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {
            "valid": True, "installed": False, "label": installer.LABEL, "changes_made": False})
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.destination.parent.exists())

    def test_conflicting_definition_is_never_overwritten(self):
        self.destination.parent.mkdir(parents=True)
        other = dict(self.spec, KeepAlive=False)
        self.destination.write_bytes(plistlib.dumps(other))
        before = self.snapshot()
        fake = SimulatedLaunchctl(self.spec)
        with self.assertRaisesRegex(RuntimeError, "different service definition"):
            self.install(fake)
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.snapshot(), before)

    def test_symbolic_link_definition_is_never_replaced(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.symlink_to(self.source)
        before = self.source.read_bytes()
        fake = SimulatedLaunchctl(self.spec)
        with self.assertRaisesRegex(RuntimeError, "symbolic-link"):
            self.install(fake)
        self.assertEqual(fake.calls, [])
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.source.read_bytes(), before)

    def test_existing_unmatched_job_is_not_changed(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_bytes(self.source.read_bytes())
        fake = SimulatedLaunchctl(self.spec, loaded=True, output="another checkout and command")
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "could not be matched"):
            self.install(fake)
        self.assertEqual([call[0] for call in fake.calls], ["print"])
        self.assertEqual(self.snapshot(), before)

    def test_repeated_install_is_idempotent_and_label_scoped(self):
        fake = SimulatedLaunchctl(self.spec)
        first = self.install(fake)
        definition = self.destination.read_bytes()
        stat = self.destination.stat()
        second = self.install(fake)
        self.assertTrue(first["installed"] and second["installed"])
        self.assertEqual(second["state"], "registered_collection_unverified")
        self.assertEqual(self.destination.read_bytes(), definition)
        self.assertEqual(self.destination.stat().st_ino, stat.st_ino)
        self.assertEqual(self.destination.stat().st_mtime_ns, stat.st_mtime_ns)
        self.assertEqual(stat.st_mode & 0o777, 0o644)
        self.assertEqual([c[0] for c in fake.calls].count("bootstrap"), 1)
        for call in fake.calls:
            if call[0] == "bootstrap":
                self.assertEqual(call, ("bootstrap", "gui/501", str(self.destination)))
            else:
                self.assertEqual(call[1], "gui/501/" + installer.LABEL)

    def test_existing_collector_is_preserved_in_standby(self):
        self.status(pid=57732, updated_at=time.time())
        status_before = (self.data / "service-status.json").read_bytes()
        fake = SimulatedLaunchctl(self.spec)
        with self.held_lock() as lock:
            before = (lock.read_bytes(), lock.stat().st_ino)
            result = self.install(fake)
            self.assertEqual(result["state"], "registered_awaiting_takeover")
            self.assertFalse(result["collection_healthy"])
            self.assertFalse(result["current_process_terminated"])
            self.assertFalse(result["sleep_settings_changed"])
            self.assertTrue(installer.collector_locked(self.data))
            self.assertEqual((lock.read_bytes(), lock.stat().st_ino), before)
        self.assertEqual((self.data / "service-status.json").read_bytes(), status_before)
        self.assertEqual(json.loads((self.data / "autostart-installation.json").read_text()), result)
        self.assertTrue(all(c[0] in {"print", "enable", "bootstrap"} for c in fake.calls))

    def test_bootstrap_failure_preserves_collector_and_does_not_record_success(self):
        fake = SimulatedLaunchctl(self.spec, bootstrap_error=True)
        with self.held_lock() as lock:
            before = lock.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "synthetic registration failure"):
                self.install(fake)
            self.assertTrue(installer.collector_locked(self.data))
            self.assertEqual(lock.read_bytes(), before)
        self.assertFalse((self.data / "autostart-installation.json").exists())

    def test_real_flock_probe_does_not_create_or_remove_lock(self):
        self.assertFalse(installer.collector_locked(self.data))
        self.assertFalse((self.data / "collector.lock").exists())
        with self.held_lock() as lock:
            before = (lock.read_bytes(), lock.stat().st_ino)
            self.assertTrue(installer.collector_locked(self.data))
        self.assertFalse(installer.collector_locked(self.data))
        self.assertEqual((lock.read_bytes(), lock.stat().st_ino), before)

    def test_verified_state_requires_pid_fresh_running_status_and_lock(self):
        output = "\tpid = 12345\n"
        self.status()
        self.assertEqual(installer.inspect_service(output, self.data, now=1000)["state"],
                         "registered_collection_unverified")
        with self.held_lock():
            result = installer.inspect_service(output, self.data, now=1000)
            self.assertEqual(result["state"], "launchd_collector_verified")
            self.assertTrue(result["collection_healthy"])
            for cycle in ("partial", "runtime_unavailable", "capacity_blocked", None):
                with self.subTest(cycle=cycle):
                    self.status(last_cycle_status=cycle)
                    result = installer.inspect_service(output, self.data, now=1000)
                    self.assertEqual(result["state"], "launchd_collector_verified")
                    self.assertFalse(result["collection_healthy"])
            for updated in (819, 1001, None, True, "990", float("nan"), float("inf")):
                with self.subTest(updated=updated):
                    self.status(updated_at=updated)
                    self.assertEqual(installer.inspect_service(output, self.data, now=1000)["state"],
                                     "registered_collection_unverified")
            self.status(status="stopped")
            self.assertEqual(installer.inspect_service(output, self.data, now=1000)["state"],
                             "registered_collection_unverified")
            self.status(updated_at=820)
            self.assertEqual(installer.inspect_service(output, self.data, now=1000)["state"],
                             "launchd_collector_verified")

    def test_other_or_unknown_launchd_pid_is_standby_only(self):
        self.status()
        with self.held_lock():
            for output in ("pid = 67890\n", "state = waiting\n"):
                with self.subTest(output=output):
                    result = installer.inspect_service(output, self.data, now=1000)
                    self.assertEqual(result["state"], "registered_awaiting_takeover")
                    self.assertFalse(result["collection_healthy"])

    def test_missing_or_invalid_status_is_unverified(self):
        path = self.data / "service-status.json"
        with self.held_lock():
            for body in (None, "broken JSON", "[]", "null", '"text"'):
                with self.subTest(body=body):
                    if body is not None:
                        path.write_text(body)
                    result = installer.inspect_service("pid = 12345\n", self.data, now=1000)
                    self.assertEqual(result["state"], "registered_collection_unverified")
                    self.assertFalse(result["collection_healthy"])


if __name__ == "__main__":
    unittest.main()
