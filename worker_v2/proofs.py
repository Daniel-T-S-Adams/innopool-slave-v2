"""TIG output metadata and whole-benchmark Merkle proofs (nonce starts at zero)."""

import json

from blake3 import blake3

from .state import StateError


def _json(value):
    # serde_json emits UTF-8 strings. This matters for a solution containing
    # non-ASCII characters; ASCII-only solutions match the legacy implementation.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def leaf_hash(leaf):
    required = {"nonce", "runtime_signature", "fuel_consumed", "solution", "cpu_arch"}
    if set(leaf) != required or leaf["cpu_arch"] not in ("amd64", "arm64") or not isinstance(leaf["solution"], str):
        raise StateError("runtime output is not the pinned TIG leaf format")
    for field in ("nonce", "runtime_signature", "fuel_consumed"):
        if type(leaf[field]) is not int or not 0 <= leaf[field] < 2**64:
            raise StateError("runtime metadata must fit protocol uint64 fields")
    signature = int.from_bytes(blake3(_json(leaf["solution"])).digest()[:8], "little")
    metadata = {field: leaf[field] for field in ("nonce", "runtime_signature", "fuel_consumed")}
    metadata["solution_signature"] = signature
    return blake3(_json(metadata)).digest()


class BenchmarkTree:
    def __init__(self, results, count):
        if type(count) is not int or count <= 0 or set(results) != set(range(count)):
            raise StateError("whole-benchmark result must cover every nonce exactly once")
        self.results = results
        hashes, self.qualities = [], []
        for nonce in range(count):
            leaf, quality = results[nonce]
            if leaf.get("nonce") != nonce:
                raise StateError("leaf position differs from its nonce")
            hashes.append(leaf_hash(leaf))
            self.qualities.append(quality)
        self.levels = [hashes]
        while len(self.levels[-1]) > 1:
            previous = self.levels[-1]
            self.levels.append([blake3(previous[index] + previous[index+1]).digest()
                               if index+1 < len(previous) else previous[index] for index in range(0, len(previous), 2)])
        self.root = self.levels[-1][0].hex()

    def result(self):
        return {"merkle_root": self.root, "solution_quality": self.qualities}

    def proofs(self, nonces):
        if not isinstance(nonces, list) or any(type(nonce) is not int or nonce not in self.results for nonce in nonces):
            raise StateError("requested proof nonce is outside this benchmark")
        if len(set(nonces)) != len(nonces):
            raise StateError("duplicate sampled nonce")
        result = []
        for nonce in sorted(nonces):
            position, branch = nonce, []
            for depth, level in enumerate(self.levels[:-1]):
                sibling = position ^ 1
                if sibling < len(level):
                    branch.append(f"{depth:02x}" + level[sibling].hex())
                position //= 2
            result.append({"leaf": self.results[nonce][0], "branch": "".join(branch)})
        return {"merkle_proofs": result}
