"""A single-machine reference runner owning an entire benchmark at a time."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
from urllib.parse import quote

from .client import ProtocolError
from .proofs import BenchmarkTree, leaf_hash
from .state import StateError, canonical, digest
from .runtime import ARM_TYPES,CPU_TYPES


TERMINAL = {"active", "verification_failed", "expired", "rejected", "cancelled"}


class Runner:
    def __init__(self, client, store, runtime, *, resource, compute_type, workers=1):
        if resource not in ("CPU", "GPU") or type(workers) is not int or workers < 1:
            raise StateError("offer one CPU or GPU resource with positive worker capacity")
        expected='GPU' if compute_type=='aws_g4dn' else 'CPU' if compute_type in CPU_TYPES else None
        if expected!=resource or (getattr(runtime,'arch',None) and (compute_type in ARM_TYPES)!=(runtime.arch=='arm64')):
            raise StateError('compute type must match the offered resource and machine architecture')
        self.client, self.store, self.runtime = client, store, runtime
        self.offer = {"resource": resource, "compute_type": compute_type, "capacity": {"workers": workers}}
        self.workers = workers

    def step(self, *, drain=False):
        capabilities = self.client.capabilities()
        member = self.client.call("GET", "/api/v2/member/balance")
        self.store.bind(self.client.origin, str(member["id"]))
        request = self.store.unfinished()
        if request is None:
            if drain or not capabilities.get("work_enabled"):
                return "idle"
            request = self.store.request(self.offer)  # Commit request key before POST.
        if request["server_id"] is None:
            if not capabilities.get("work_enabled"):
                return "waiting"
            response = self.client.call("POST", "/api/v2/work-requests",
                {**json.loads(request["offer"]), "request_key": request["request_key"]})
            self.store.link_request(request["request_key"], response["id"], response.get("benchmark_id"))
            request = self.store.unfinished()
        state = self.client.call("GET", "/api/v2/work-requests/" + quote(request["server_id"], safe=""))
        if state["state"] in TERMINAL and not state.get("benchmark_id"):
            self.store.finish(request["request_key"], state["state"])
            return state["state"]
        if not state.get("benchmark_id"):
            if state["state"] == "queued" and not drain:
                self.client.call("POST", "/api/v2/work-requests/" + quote(request["server_id"], safe="") + "/refresh", {})
            return "waiting"
        identity = state["benchmark_id"]
        self.store.link_request(request["request_key"], request["server_id"], identity)
        remote = self.client.benchmark(identity)
        if remote["state"] in TERMINAL:
            try:
                saved = self.store.assignment(identity)
            except StateError:
                saved = None
            if saved:
                self.runtime.release(json.loads(saved["payload"]))
            self.store.finish(request["request_key"], remote["state"])
            return remote["state"]
        assignment = self.store.save_assignment(identity, remote["assignment_payload"], remote["assignment_digest"])
        self.runtime.validate(assignment, json.loads(request["offer"]))
        local = self.store.assignment(identity)
        if not local["acknowledged_at"]:
            # Saved bytes and digest survive even if the acknowledgement response
            # is lost. A committed server timestamp can be recovered by GET.
            if remote.get("handed_over_at"):
                acknowledgement = remote
            else:
                acknowledgement = self.client.acknowledge(identity, local["digest"])
            if acknowledgement.get("assignment_digest") != local["digest"]:
                raise ProtocolError("pool acknowledged a different assignment")
            self.store.acknowledge(identity, acknowledgement.get("handed_over_at"))
        results = self.store.nonces(identity)
        count = assignment["num_nonces"]
        if type(count) is not int or count <= 0:
            raise StateError("assignment has invalid whole-benchmark nonce count")
        completed = set(results)
        if len(completed) != count:
            missing = iter(nonce for nonce in range(count) if nonce not in completed)
            self.runtime.prepare(assignment)
            # Only the main thread writes SQLite. Each nonce's complete leaf and
            # verifier quality are durable before another restart can need them.
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {}
                while True:
                    # A completed Future holds its entire solution. Bound the
                    # in-flight set and discard saved futures, including when
                    # one benchmark contains many large solution leaves.
                    while len(futures) < self.workers:
                        nonce = next(missing, None)
                        if nonce is None:
                            break
                        futures[executor.submit(self.runtime.compute, assignment, nonce)] = nonce
                    if not futures:
                        break
                    ready, _ = wait(futures, return_when=FIRST_COMPLETED)
                    while ready:
                        future = ready.pop()
                        nonce = futures.pop(future)
                        leaf, quality = future.result()
                        leaf_hash(leaf)
                        self.store.save_nonce(identity, nonce, leaf, quality)
                        del future, leaf
            results = self.store.nonces(identity)
        tree = BenchmarkTree(results, count)
        path = "/api/v2/benchmarks/" + quote(identity, safe="")
        if not self.store.assignment(identity)["result_sent"]:
            result = self.client.call("POST", path + "/results", tree.result())
            if result.get("stored") is not True:
                raise ProtocolError("pool did not durably store the benchmark result")
            self.store.result_sent(identity)
        remote = self.client.benchmark(identity)
        if remote["state"] in TERMINAL:
            self.runtime.release(assignment)
            self.store.finish(request["request_key"], remote["state"])
            return remote["state"]
        nonces = remote.get("sampled_nonces")
        if nonces is not None:
            proofs = tree.proofs(nonces)
            proof_digest = digest(canonical(proofs))
            if self.store.assignment(identity)["proofs_digest"] != proof_digest:
                result = self.client.call("POST", path + "/proofs", proofs)
                if result.get("stored") is not True:
                    raise ProtocolError("pool did not durably store the proofs")
                self.store.proofs_sent(identity, proof_digest)
        return "awaiting_verification"
