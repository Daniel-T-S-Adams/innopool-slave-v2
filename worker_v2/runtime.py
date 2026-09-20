"""Pinned Docker runtime, scoped to this worker's own benchmark containers."""

import hashlib
import io
import json
from pathlib import Path
import platform
import re
import subprocess
import tarfile
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .client import NoRedirect
from .proofs import leaf_hash
from .state import StateError, canonical


ARM_TYPES = {"aws_t4g", "aws_c7g", "aws_m7g"}
CPU_TYPES = ARM_TYPES | {"aws_t3", "aws_t3a", "aws_c7i", "aws_c7a", "aws_m7i", "aws_m7a"}


class DockerRuntime:
    def __init__(self, directory, images, *, binary_hosts=("mainnet-api.tig.foundation",),
                 nonce_timeout=1800, command=subprocess.run):
        self.directory = Path(directory).resolve() / "runtime"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.images, self.binary_hosts, self.nonce_timeout, self.command = images, set(binary_hosts), nonce_timeout, command
        machine = platform.machine().lower()
        self.arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
        if self.arch is None:
            raise StateError("unsupported runtime CPU architecture")
        self.namespace = hashlib.sha256(str(self.directory).encode()).hexdigest()[:12]

    def validate(self, assignment, offer):
        settings = assignment.get("settings", {})
        algorithm, challenge = settings.get("algorithm_id", ""), settings.get("challenge_id", "")
        if not re.fullmatch(r"c[0-9]+_a[0-9]+", algorithm) or not re.fullmatch(r"c[0-9]+", challenge):
            raise StateError("unexpected TIG challenge/algorithm identifier")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}",assignment.get("algorithm_name",algorithm)):
            raise StateError("unexpected algorithm archive library name")
        if any(not isinstance(settings.get(key), str) or not settings[key] for key in
               ("player_id", "block_id", "track_id")):
            raise StateError("assignment omits complete TIG settings")
        if not isinstance(assignment.get("rand_hash"), str) or not re.fullmatch(r"[0-9a-f]{32}", assignment["rand_hash"]):
            raise StateError("invalid TIG random seed")
        for key in ("num_nonces", "num_bundles", "fuel_budget"):
            if type(assignment.get(key)) is not int or assignment[key] < (0 if key == "fuel_budget" else 1):
                raise StateError("assignment has invalid runtime limits")
        if "hyperparameters" not in assignment or (assignment["hyperparameters"] is not None and not isinstance(assignment["hyperparameters"], dict)):
            raise StateError("assignment is missing hyperparameters or the null default")
        compute = assignment.get("compute_type")
        expected = "GPU" if compute == "aws_g4dn" else "CPU" if compute in CPU_TYPES else None
        if expected != offer["resource"] or compute != offer["compute_type"]:
            raise StateError("assignment differs from the offered resource")
        if (compute in ARM_TYPES) != (self.arch == "arm64"):
            raise StateError("verification compute type does not match this machine architecture")
        image = self.images.get(challenge, "")
        if not re.fullmatch(r"ghcr\.io/tig-foundation/tig-monorepo/[a-z_]+/runtime@sha256:[0-9a-f]{64}", image):
            raise StateError("challenge runtime must be an explicitly pinned official image digest")
        url = urlsplit(assignment.get("binary_url", ""))
        if url.scheme != "https" or url.hostname not in self.binary_hosts or url.username or url.password or url.fragment:
            raise StateError("algorithm download does not use an allowed HTTPS host")
        if not re.fullmatch(r"[0-9a-f]{64}", assignment.get("binary_sha256", "")):
            raise StateError("assignment must include the pool's verified binary archive checksum")

    def _paths(self, assignment):
        key = hashlib.sha256(assignment["benchmark_id"].encode()).hexdigest()[:24]
        root = self.directory / key
        return root, f"innopool-v2-{self.namespace}-{key}"

    def _run(self, args, timeout=60):
        return self.command(args, capture_output=True, text=True, timeout=timeout, check=True)

    def _inspect(self, name):
        result = self.command(["docker", "inspect", name], capture_output=True, text=True, timeout=15)
        if result.returncode:
            return None
        return json.loads(result.stdout)[0]

    def prepare(self, assignment):
        root, name = self._paths(assignment)
        root.mkdir(parents=True, exist_ok=True)
        (root / "results").mkdir(exist_ok=True)
        algorithm = assignment["settings"]["algorithm_id"]
        source_name = assignment.get("algorithm_name",algorithm)
        library = root / (algorithm + ".so")
        marker = root / "archive.sha256"
        if not library.exists() or not marker.exists() or marker.read_text() != assignment["binary_sha256"]:
            request = Request(assignment["binary_url"], headers={"User-Agent": "innopool-v2-member/2.0"})
            with build_opener(NoRedirect()).open(request, timeout=60) as response:
                archive = response.read(64*1024*1024+1)
            if len(archive) > 64*1024*1024 or hashlib.sha256(archive).hexdigest() != assignment["binary_sha256"]:
                raise StateError("algorithm archive checksum or size is invalid")
            wanted = {f"{self.arch}/{source_name}.so": library, f"ptx/{source_name}.ptx": root / (algorithm + ".ptx")}
            found, total = set(), 0
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r|gz") as tar:
                for member in tar:
                    total += member.size
                    if total > 256*1024*1024:
                        raise StateError("algorithm archive expands beyond the configured limit")
                    if member.name not in wanted:
                        continue
                    if not member.isfile() or member.size > 64*1024*1024 or member.name in found:
                        raise StateError("unsafe or duplicate algorithm archive entry")
                    wanted[member.name].write_bytes(tar.extractfile(member).read())
                    found.add(member.name)
            if f"{self.arch}/{source_name}.so" not in found:
                raise StateError("algorithm archive has no library for this CPU architecture")
            if assignment["compute_type"] == "aws_g4dn" and f"ptx/{source_name}.ptx" not in found:
                raise StateError("GPU algorithm archive has no PTX")
            marker.write_text(assignment["binary_sha256"])
        image = self.images[assignment["settings"]["challenge_id"]]
        existing = self._inspect(name)
        if existing:
            labels = existing["Config"].get("Labels", {})
            if labels.get("innopool.v2.owner") != self.namespace or labels.get("innopool.v2.benchmark") != assignment["benchmark_id"] or existing["Config"]["Image"] != image:
                raise StateError("existing container is not this worker's pinned benchmark runtime")
            # Clear this benchmark's leftover nonce processes after a worker
            # crash before replaying unfinished nonces. Other containers are
            # never inspected by name patterns or signalled.
            self._run(["docker", "restart", "--time", "5", name])
            return
        args = ["docker", "run", "--detach", "--name", name, "--network", "none", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--label", "innopool.v2.owner=" + self.namespace,
                "--label", "innopool.v2.benchmark=" + assignment["benchmark_id"],
                "--mount", f"type=bind,src={root},dst=/work,readonly",
                "--mount", f"type=bind,src={root / 'results'},dst=/work/results", "--workdir", "/work"]
        if assignment["compute_type"] == "aws_g4dn":
            args += ["--gpus", "all", "--env", "NVIDIA_DRIVER_CAPABILITIES=compute,utility"]
        self._run(args + [image, "sleep", "infinity"], timeout=300)

    def compute(self, assignment, nonce):
        root, name = self._paths(assignment)
        algorithm = assignment["settings"]["algorithm_id"]
        settings = canonical(assignment["settings"])
        args = ["docker", "exec", name, "tig-runtime", settings, assignment["rand_hash"], str(nonce),
                f"/work/{algorithm}.so", "--fuel", str(assignment["fuel_budget"]), "--output", "/work/results"]
        if assignment["hyperparameters"] is not None:
            args += ["--hyperparameters", canonical(assignment["hyperparameters"])]
        ptx = ["--ptx", f"/work/{algorithm}.ptx"] if assignment["compute_type"] == "aws_g4dn" else []
        self._run(args + ptx, timeout=self.nonce_timeout)
        verified = self._run(["docker", "exec", name, "tig-verifier", settings, assignment["rand_hash"],
                              str(nonce), f"/work/results/{nonce}.json"] + ptx, timeout=self.nonce_timeout)
        lines = verified.stdout.strip().splitlines()
        if not lines or not re.fullmatch(r"quality: -?[0-9]+", lines[-1]):
            raise StateError("TIG verifier did not return a solution quality")
        leaf = json.loads((root / "results" / f"{nonce}.json").read_text())
        leaf_hash(leaf)
        if leaf["nonce"] != nonce:
            raise StateError("TIG runtime returned another nonce")
        return leaf, int(lines[-1].split(": ")[1])

    def release(self, assignment):
        _, name = self._paths(assignment)
        existing = self._inspect(name)
        if existing:
            labels = existing["Config"].get("Labels", {})
            if labels.get("innopool.v2.owner") != self.namespace or labels.get("innopool.v2.benchmark") != assignment["benchmark_id"]:
                raise StateError("refusing to stop a container owned by another deployment")
            self._run(["docker", "rm", "--force", name])
