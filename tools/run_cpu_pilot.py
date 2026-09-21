#!/usr/bin/env python3
"""Start one CPU worker inside this host's shared, bounded pilot slice."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker_v2.resources import RuntimeLimits
from worker_v2.state import StateError


SLICE = "innopoolv2pilot.slice"
GROUP = Path("/sys/fs/cgroup") / SLICE
GIB = 1024 ** 3


def check_budget(group=GROUP):
    quota, period = (group / "cpu.max").read_text().split()
    if quota == "max" or not 0 < int(quota) <= int(period):
        raise StateError("pilot slice must cap combined CPU use at one core or less")
    memory = int((group / "memory.max").read_text())
    if not 0 < memory <= 2 * GIB:
        raise StateError("pilot slice must cap combined memory at 2 GiB or less")
    if (group / "memory.swap.max").read_text().strip() != "0":
        raise StateError("pilot slice must disable swap")
    if not 0 < int((group / "pids.max").read_text()) <= 256:
        raise StateError("pilot slice must cap combined process/thread count at 256 or less")
    current = int((group / "memory.current").read_text())
    return max(0, memory - current)


def check_headroom(directory, remaining_memory, *, meminfo=Path("/proc/meminfo")):
    fields = dict(line.split(":", 1) for line in meminfo.read_text().splitlines())
    available = int(fields["MemAvailable"].split()[0]) * 1024
    if available - remaining_memory < GIB:
        raise StateError("not enough spare RAM for the pilot budget plus 1 GiB of host headroom; try later")
    if shutil.disk_usage(directory).free < 10 * GIB:
        raise StateError("pilot needs at least 10 GiB of free disk space for retained evidence")


def check_worker(directory):
    record = json.loads((directory / "installation-v2.json").read_text())
    if record.get("kind") != "innopool-v2-worker" or record.get("directory") != str(directory):
        raise StateError("use an owned, pinned v2 worker installation")
    config = json.loads((directory / "worker.json").read_text())
    if config.get("resource") != "CPU" or type(config.get("workers")) is not int or config["workers"] != 1:
        raise StateError("local pilot requires CPU only and workers=1")
    limits = RuntimeLimits.parse(config.get("runtime_limits"))
    if (not limits or limits.cgroup_parent != SLICE or limits.cpu_millis > 1000
            or limits.memory_mib > 1280 or limits.pids_limit > 128):
        raise StateError("pilot runtime requires the shared slice, at most one CPU, 1280 MiB and 128 threads/processes")
    if not (directory / "run").is_file() or (directory / "run").is_symlink():
        raise StateError("pinned worker launcher is missing or redirected")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", help="owned worker installation")
    parser.add_argument("--check", action="store_true", help="check host limits/headroom without starting a worker")
    parser.add_argument("--drain", action="store_true", help="recover saved work without requesting a new benchmark")
    args = parser.parse_args(argv)
    try:
        if os.geteuid() != 0:
            raise StateError("this local pilot launcher requires the operator's root session")
        if args.directory is None and not args.check:
            raise StateError("supply a worker installation, or use --check for the host only")
        directory = args.directory.resolve() if args.directory else Path.cwd()
        remaining = check_budget()
        check_headroom(directory, remaining)
        # Explicitly use this machine's daemon. A remote Docker context would
        # escape the host's shared resource accounting.
        env = {key: value for key, value in os.environ.items() if key not in ("DOCKER_CONTEXT", "DOCKER_HOST")}
        info = subprocess.run(["docker", "--host", "unix:///var/run/docker.sock", "info", "--format",
                               "{{json .CgroupDriver}} {{json .CgroupVersion}}"],
                              env=env, check=True, capture_output=True, text=True, timeout=15)
        if info.stdout.strip() != '"systemd" "2"':
            raise StateError("local pilot requires Docker's systemd driver and cgroup v2")
        if args.directory:
            check_worker(directory)
        if args.check:
            print("Pilot host limits/headroom verified; no worker started.")
            return 0
        # One fixed unit name prevents two member workers running at once.
        # Docker children join the same slice through runtime_limits.
        result = subprocess.run(["systemd-run", "--wait", "--collect",
            "--unit=innopoolv2pilot-worker", "--slice=" + SLICE,
            "--property=Nice=10", "--property=CPUWeight=10", "--property=IOWeight=10",
            "--property=UnsetEnvironment=DOCKER_CONTEXT",
            "--setenv=DOCKER_HOST=unix:///var/run/docker.sock",
            "--setenv=PYTHONDONTWRITEBYTECODE=1", str(directory / "run"), "--require-resource-limits",
            *(["--drain"] if args.drain else [])], check=False)
        return result.returncode
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("CPU pilot stopped: " + (str(error) if isinstance(error, StateError) else type(error).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
