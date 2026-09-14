#!/usr/bin/env python3
"""Prepare a reviewable macOS login-service definition; does not install it."""

import argparse
from pathlib import Path
import plistlib
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
data_dir = Path(args.data_dir).resolve()
payload = {
    "Label": "com.satellite-research.collector",
    "ProgramArguments": [sys.executable, "-m", "satresearch", "--data-dir", str(data_dir),
                         "--config", str(Path(args.config).resolve()), "service"],
    "WorkingDirectory": str(root),
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 60,
    "ProcessType": "Background",
    "LowPriorityIO": True,
    "StandardOutPath": str(data_dir / "service.stdout.log"),
    "StandardErrorPath": str(data_dir / "service.stderr.log"),
}
dest = Path(args.output)
dest.parent.mkdir(parents=True, exist_ok=True)
if dest.exists():
    raise SystemExit("Refusing to overwrite an existing service definition")
dest.write_bytes(plistlib.dumps(payload))
print(dest)
