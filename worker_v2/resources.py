"""Explicit container limits and optional containment of the worker itself."""

from dataclasses import dataclass
from pathlib import Path
import re

from .state import StateError


@dataclass(frozen=True)
class RuntimeLimits:
    cpu_millis: int
    memory_mib: int
    pids_limit: int
    cgroup_parent: str | None = None

    @classmethod
    def parse(cls, value):
        if value is None:
            return None
        required = {"cpu_millis", "memory_mib", "pids_limit"}
        if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - {"cgroup_parent"}:
            raise StateError("runtime_limits requires cpu_millis, memory_mib and pids_limit; only cgroup_parent is optional")
        for key, minimum, maximum in (("cpu_millis", 1, 4096000), ("memory_mib", 6, 1048576), ("pids_limit", 1, 65536)):
            if type(value[key]) is not int or not minimum <= value[key] <= maximum:
                raise StateError(f"runtime_limits.{key} must be an integer between {minimum} and {maximum}")
        parent = value.get("cgroup_parent")
        if "cgroup_parent" in value and (not isinstance(parent, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.slice", parent)):
            raise StateError("runtime_limits.cgroup_parent must name a systemd slice")
        return cls(**value)

    @property
    def host_config(self):
        memory = self.memory_mib * 1024 * 1024
        result = {"NanoCpus": self.cpu_millis * 1000000, "Memory": memory,
                  "MemorySwap": memory, "PidsLimit": self.pids_limit}
        if self.cgroup_parent:
            result["CgroupParent"] = self.cgroup_parent
        return result

    def docker_args(self):
        memory = str(self.memory_mib) + "m"
        args = ["--cpus", f"{self.cpu_millis // 1000}.{self.cpu_millis % 1000:03d}",
                "--memory", memory, "--memory-swap", memory, "--pids-limit", str(self.pids_limit)]
        if self.cgroup_parent:
            args += ["--cgroup-parent", self.cgroup_parent]
        return args

    def matches(self, host_config):
        return all(host_config.get(key) == value for key, value in self.host_config.items())

    def check_process_group(self, *, proc=Path("/proc/self/cgroup"), root=Path("/sys/fs/cgroup")):
        """A configured shared slice must also contain the Python worker."""
        if not self.cgroup_parent:
            return
        try:
            groups = [line[3:] for line in proc.read_text().splitlines() if line.startswith("0::/")]
            if len(groups) != 1 or self.cgroup_parent not in Path(groups[0]).parts:
                raise StateError("start this worker inside its configured systemd slice")
            parts = Path(groups[0]).parts[1:]
            parent = root.joinpath(*parts[:parts.index(self.cgroup_parent) + 1])
            quota, period = parent.joinpath("cpu.max").read_text().split()
            if quota == "max" or int(quota) <= 0 or int(period) <= 0:
                raise StateError("the shared worker slice needs a hard CPU limit")
            memory = parent.joinpath("memory.max").read_text().strip()
            if memory == "max" or int(memory) <= 0:
                raise StateError("the shared worker slice needs a hard memory limit")
            if parent.joinpath("memory.swap.max").read_text().strip() != "0":
                raise StateError("the shared worker slice must disable swap")
        except (OSError, ValueError) as error:
            if isinstance(error, StateError):
                raise
            raise StateError("cannot verify the worker's shared cgroup limits") from error
