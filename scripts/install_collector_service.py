#!/usr/bin/env python3
"""User-run macOS login-service installer. --check-only makes no changes."""

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time

LABEL = "com.satellite-research.collector"


def validate(source):
    spec = plistlib.loads(Path(source).read_bytes())
    expected_keys = {"Label", "ProgramArguments", "WorkingDirectory", "RunAtLoad", "KeepAlive",
                     "ThrottleInterval", "ProcessType", "LowPriorityIO", "StandardOutPath", "StandardErrorPath"}
    if not isinstance(spec, dict) or set(spec) != expected_keys or spec.get("Label") != LABEL:
        raise ValueError("Unexpected service definition; use prepare_collector_service.py")
    args = spec.get("ProgramArguments", [])
    if (not isinstance(args, list) or len(args) != 8 or args[1:4] != ["-m", "satresearch", "--data-dir"]
            or args[5] != "--config" or args[7] != "service"):
        raise ValueError("Only the satellite-research collector command is accepted")
    if any(not isinstance(value, str) for value in args):
        raise ValueError("Service arguments must be strings")
    root, data, config, executable = map(Path, (spec["WorkingDirectory"], args[4], args[6], args[0]))
    if not all(p.is_absolute() for p in (root, data, config, executable)):
        raise ValueError("Service paths must be absolute")
    if not (root / "satresearch/__main__.py").is_file() or not data.is_dir() or not config.is_file():
        raise ValueError("The checkout, data directory and configuration must already exist")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("Configured Python interpreter is unavailable")
    if (spec["RunAtLoad"] is not True or spec["KeepAlive"] is not True
            or spec["ThrottleInterval"] != 60 or spec["ProcessType"] != "Background"
            or spec["LowPriorityIO"] is not True):
        raise ValueError("Unexpected restart policy")
    if (spec["StandardOutPath"] != str(data / "service.stdout.log")
            or spec["StandardErrorPath"] != str(data / "service.stderr.log")):
        raise ValueError("Service logs must remain in the configured data directory")
    return spec


def launchctl(*args):
    return subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True, timeout=20)


def require_success(result, action):
    if result.returncode:
        raise RuntimeError(action + " failed: " + (result.stderr or result.stdout).strip())


def collector_locked(data):
    """Probe the real lock; never delete it or trust a saved PID as ownership."""
    lock = Path(data) / "collector.lock"
    if not lock.exists():
        return False
    with lock.open("r+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream, fcntl.LOCK_UN)
    return False


def inspect_service(job_output, data, now=None):
    now = time.time() if now is None else now
    match = re.search(r"^\s*pid = ([0-9]+)\s*$", job_output, re.MULTILINE)
    job_pid = int(match.group(1)) if match else None
    exit_match = re.search(r"^\s*last exit code = (-?[0-9]+)\s*$", job_output, re.MULTILINE)
    last_exit = int(exit_match.group(1)) if exit_match else None
    state_match = re.search(r"^\s*state = (.+?)\s*$", job_output, re.MULTILINE)
    try:
        status = json.loads((Path(data) / "service-status.json").read_text())
    except (FileNotFoundError, ValueError):
        status = {}
    if not isinstance(status, dict):
        status = {}
    updated = status.get("updated_at")
    age = now-updated if isinstance(updated, (float, int)) and not isinstance(updated, bool) and math.isfinite(updated) else None
    fresh = age is not None and 0 <= age <= 180
    lock_held = collector_locked(data)
    same_pid = job_pid is not None and status.get("pid") == job_pid
    existing_active = bool(lock_held and fresh and status.get("status") == "running" and not same_pid)
    if same_pid and fresh and lock_held and status.get("status") == "running":
        state = "launchd_collector_verified"
    elif job_pid is None and last_exit is not None and last_exit != 0:
        state = "registered_startup_failed"
    else:
        state = "registered_collection_unverified"
    return {"state": state, "launchd_pid": job_pid, "observed_service_pid": status.get("pid"),
            "last_exit_code": last_exit, "launchd_state": state_match.group(1) if state_match else None,
            "existing_collector_active": existing_active,
            "heartbeat_age_s": age, "writer_lock_held": lock_held,
            "last_cycle_status": status.get("last_cycle_status"),
            "collection_healthy": state == "launchd_collector_verified" and status.get("last_cycle_status") == "completed"}


def install(source, home=None, uid=None):
    if sys.platform != "darwin":
        raise RuntimeError("This installer is for macOS")
    uid = os.getuid() if uid is None else uid
    if uid == 0:
        raise RuntimeError("Run as your normal logged-in user, without sudo")
    spec = validate(source)
    data = Path(spec["ProgramArguments"][4])
    destination = (Path.home() if home is None else Path(home)) / "Library/LaunchAgents" / (LABEL + ".plist")
    domain, target = "gui/%d" % uid, "gui/%d/%s" % (uid, LABEL)
    if destination.is_symlink():
        raise RuntimeError("Refusing to replace a symbolic-link service definition")
    if destination.exists() and plistlib.loads(destination.read_bytes()) != spec:
        raise RuntimeError("A different service definition already exists; it was left unchanged")
    before = launchctl("print", target)
    if before.returncode == 0:
        if not destination.exists() or any(value not in before.stdout for value in
                                          (spec["WorkingDirectory"], spec["ProgramArguments"][4], spec["ProgramArguments"][6])):
            raise RuntimeError("An existing job could not be matched to this definition; it was left unchanged")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        # Exclusive creation prevents overwriting a job created during validation.
        with destination.open("xb") as stream:
            stream.write(plistlib.dumps(spec))
        destination.chmod(0o644)
    require_success(launchctl("enable", target), "Enabling automatic restart")
    if before.returncode:
        require_success(launchctl("bootstrap", domain, str(destination)), "Registering the login service")
    after = launchctl("print", target)
    require_success(after, "Verifying service registration")
    result = {"installed": True, "checked_at": time.time(), "definition": str(destination), "label": LABEL,
              "starts_at_login": True, "restart_on_exit": True, "sleep_settings_changed": False,
              "current_process_terminated": False, **inspect_service(after.stdout, data)}
    # No PID is killed and no lock is removed. KeepAlive retries after the old collector exits.
    path = data / "autostart-installation.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, indent=2) + "\n")
    temp.replace(path)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("definition", help="Prepared collector plist")
    parser.add_argument("--check-only", action="store_true", help="Validate the definition without installing or starting anything")
    args = parser.parse_args(argv)
    try:
        if args.check_only:
            spec = validate(args.definition)
            print(json.dumps({"valid": True, "installed": False, "label": spec["Label"],
                              "changes_made": False}, indent=2))
            return 0
        result = install(args.definition)
        print("Automatic login and exit recovery are registered with macOS.")
        if result["state"] == "launchd_collector_verified":
            print("Verified the macOS-managed collector. Latest collection result: " + str(result["last_cycle_status"]))
        elif result["state"] == "registered_startup_failed":
            print("The registered job exited with an error. Inspect service.stderr.log; automatic recovery is not verified.")
        else:
            print("Registration succeeded; a fresh macOS-managed collection cycle has not yet been verified.")
        if result["existing_collector_active"]:
            print("The existing collector is still active. That does not prove the new job can start or take over.")
        print("Collection still requires an awake Mac and a running GEV. Weekly approval rules are unchanged.")
        print(json.dumps(result, indent=2))
        return 2 if result["state"] == "registered_startup_failed" else 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("Automatic restart installation was not fully verified: " + str(exc), file=sys.stderr)
        print("The installer did not terminate the existing collector or remove its lock.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
