# Member master with SSH helpers

Implemented on 12 October 2026. This optional mode lets one pool member combine
local nonce computation and explicitly configured helper servers. The default
installer still starts a local worker; it does not provision helper accounts,
keys, services or networking. The pool API and benchmark format are unchanged.

## How it works

The master saves and acknowledges the complete pool assignment, then sends its
exact payload, digest and confirmed handover timestamp to each helper over SSH.
Helpers check the verification compute type, architecture, runtime image and
archive hash. They compute assigned nonces and save complete outputs in their
own SQLite store before replying. The master durably saves every returned leaf
and quality, combines all nonces into one result, and supplies the pool's exact
authoritative sampled proofs.

Only the master uses `POOL_V2_EXECUTION_TOKEN`. Helpers run
`python -m worker_v2.helper`; they never create pool work requests. No helper HTTP
port or pool/TIG credential is required. SSH host keys are checked strictly;
record the host key during setup, rather than allowing automatic acceptance in
the worker. Use a dedicated SSH key for the master and restrict its helper
authorization to the configured helper command.

## Configuration

Install the same pinned worker source and BLAKE3 dependency on both machines.
Use separate data directories from existing worker installations. The helper
uses a bounded systemd slice and Docker with the systemd cgroup v2 driver. Its
slice must have hard CPU and memory limits and `MemorySwapMax=0`.

The master keeps its ordinary worker configuration and adds:

```json
{
  "master_id": "member-master-one",
  "workers": 2,
  "nonce_timeout_seconds": 480,
  "helpers": [{
    "host": "helper.example",
    "user": "root",
    "identity_file": "/opt/member-master/helper-key",
    "known_hosts_file": "/opt/member-master/known_hosts",
    "python": "/opt/member-helper/venv/bin/python",
    "code_directory": "/opt/member-helper/code",
    "config": "/opt/member-helper/helper.json",
    "slice": "innopoolmemberhelper.slice",
    "workers": 2
  }]
}
```

`workers` remains the master's local concurrency. Each helper contributes its
configured additional concurrency: the example offers four workers for one
benchmark. Set local `workers` to zero for a master that only coordinates.
Aggregate capacity is limited to 4,096, including local work. Each helper entry
must identify a distinct helper configuration. Allocate the underlying compute
once across concurrent masters and benchmarks.

The helper configuration is:

```json
{
  "master_id": "member-master-one",
  "data_directory": "/opt/member-helper/data",
  "resource": "CPU",
  "compute_type": "aws_c7g",
  "workers": 2,
  "runtime_images": {"c003": "COPY_THE_EXACT_PINNED_IMAGE_FROM_THE_MASTER"},
  "nonce_timeout_seconds": 480,
  "runtime_limits": {
    "cpu_millis": 2000,
    "memory_mib": 4096,
    "pids_limit": 256,
    "cgroup_parent": "innopoolmemberhelper.slice"
  }
}
```

The master and helper must use the same `master_id`, resource, verification
compute type, complete runtime-image mapping and nonce timeout. The image
placeholder above must be replaced with actual official images pinned by
SHA-256. The helper's slice must match both configurations. The transport
starts the helper inside that slice with `systemd-run --scope`.
For legacy assignments whose archive URL points to the pool, configure the
helper's `binary_hosts` with the pool API hostname plus
`mainnet-api.tig.foundation` and `media.githubusercontent.com`.

## Recovery and limits

The master verifies all configured helpers before offering their aggregate
capacity for new work. After confirmed handover, a disconnected helper can be
omitted while the remaining compatible compute resumes unfinished nonces.
Completed master outputs survive restarts; reconnecting helpers reuse their
saved outputs. A helper process lock prevents competing sessions from restarting
its runtime concurrently. An old session finishes bounded in-flight work and
cleans up after input closes; a new session may need to retry until that lock
is released.

SSH/RPC timeouts stop waiting and preserve master evidence. Per-nonce timeout
is still **not a whole-benchmark deadline or a capacity guarantee**. Measure
the selected workload and complete minimum against the protocol lifetime
before paid precommit. More helpers do not extend that lifetime.

Keep the master assignment and complete outputs through collateral settlement
and any pending evidence requests. Helper caches also remain present; this
implementation does not guess a finalization date and delete evidence.

## Verification state

Local tests cover local/helper aggregation, exact whole-benchmark proofs,
disconnection and master restart, cached helper output, assignment/architecture
checks, strict SSH configuration, and concurrent request/response matching
through real subprocess pipes. **46 v2 tests and 17 inherited tests passed.**
Computation and the SSH executable in those tests are simulated.

A subsequent real SSH/Docker check used a workspace coordinator and an isolated
helper on `poolminer1`, with two concurrent nonces. Eight nonces from the archived
public knapsack assignment passed the actual TIG runtime/verifier in 129.45
seconds including preparation. After a new SSH session, a saved nonce was
recovered from the helper cache. This was a subset check without pool calls;
it did not complete a protocol benchmark or use the intended second server.

The subsequent complete rehearsal used `poolminer1` as master with six local
workers and six SSH helper workers on `77.42.14.166`. Both ARM64 hosts ran the
same pinned source/images and configured `aws_c7g` verification type; this does
not certify a physical cloud instance type. All **200 knapsack nonces** and
**three sampled proofs** passed. The master returned 99 results locally and
received 101 from the helper. Wall time was **15 minutes 8 seconds**, including
an intentional helper disconnect, master SIGKILL and the pause before restart.
All **105 saved outputs** survived unchanged and were reused without recomputation.

The isolated pool API accepted complete result/proof uploads and identical
retries, rejected a changed root, and preserved financial records. Protocol
receipts/sampling/activation were simulated; no paid TIG submission or production
execution token was used. Owned runtime containers were released and test units
stopped. Separate source/configuration and evidence remain on both hosts; no
autostart worker was created. Temporary slice definitions disappear on reboot
and must be installed deliberately for a persistent release.

See the pool's [full verification record](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/SSH_MEMBER_MASTER_VERIFICATION.md).
Paired production activation, actual TIG acceptance, timely job-scheduling
execution and GPU validation remain pending.
