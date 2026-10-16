# Whole-benchmark member worker

The corrected 14 October mainnet trial activated successfully at TIG height
**1383916**, around **11:35 UTC**. Master/helper saved all 4,000 outputs
(1,968/2,032); results were uploaded **12m40s after handover**.
Confirmed proof and detailed TIG records show no verification failure. All results/proofs match the stored pool
payloads. New work remains paused; reward settlement remains open. The pool
storage ordering fix is deployed. The earlier runtime-pin failure is preserved
in the
[trial record](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/MAINNET_CPU_TRIAL_20261014.md).

The first 14 October mainnet trial exposed an outdated knapsack runtime pin. It
completed and uploaded 4,000 nonces in 10m31s, then failed TIG's later solution
verification. The current 0.0.8 verifier reproduced TIG's rejection of the
0.0.7 outputs. All five corrected unpaid tracks passed: 12,400 outputs, 15 sampled proofs,
slowest 12m29s. The corrected pair is active; ordinary work remains paused. See the [actual trial record](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/MAINNET_CPU_TRIAL_20261014.md).

This branch adds a runtime release check before a new offer, an unlinked saved
offer or queued-offer refresh. It verifies the pool's release digest and checks
every configured backend against the published runtime map. A mismatch stops
new work and requires an explicit drained update of the master and helpers.
Already handed-over work can still drain; saved evidence is preserved. This
guard is served in worker `dddad9`, now paired with pool `59a3446` after
the 14 October storage fix.

`worker_v2` implements member API version `2.0`. It runs independently of the
legacy worker and owns one entire benchmark at a time. Members may run their
own compatible clients or multiple installations; the pool enforces the shared
two-slot limit for each member across CPU and GPU requests.

## Member-managed masters

Members may use the [SSH member master mode](SSH_MEMBER_MASTER_V2.md), or replace
this client with their own master, to distribute nonce computation across
compatible machines. The master uses the same
API 2.0 work request, assignment, acknowledgement, complete result and proof
routes. It remains responsible for the whole benchmark after confirmed handover.
Members implement internal transport, scheduling, recovery and output aggregation.
The pool's [member master contract](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/main/docs/MEMBER_MASTER_V2.md)
specifies that integration. Paired pool tests exercise a simulated master
combining helper outputs, recovering missing work after restart, and submitting
one complete result and sampled proofs. SSH transport and recovery passed
local tests and a real two-server rehearsal. This mode is included in the
worker served by the production pool since 13 October 2026.

Every helper used for an assignment must match its verification compute type
and compatible architecture, algorithm binary and runtime. A custom master may
offer aggregate concurrent nonce capacity across compatible machines. It must
save complete outputs durably, return one whole-benchmark root with all nonce
qualities in order, and supply exactly TIG's sampled proofs. Keep execution
credentials with the pool-facing master; helpers do not need pool credentials.

By default this implementation executes on one machine. Its `workers` setting
controls local concurrent nonce computations. Optional `helpers` configure
additional SSH compute capacity; see the member master guide.
Running several independent installations requests separate benchmarks; all
installations still share the member's two-slot limit. Sharing one benchmark
uses a member master to aggregate the outputs before upload.
Retain the required assignment and output evidence through final collateral
settlement and any pending evidence requests.

## Assignment and recovery

1. Offer exactly CPU or GPU, a compatible TIG verification compute type and
   worker capacity. Save a unique request key before contacting the pool.
2. Save the complete assignment's exact serialized bytes and verify their
   SHA-256. Validate the resource and pinned runtime configuration.
3. Acknowledge the benchmark ID and digest. Start computation only after the
   pool confirms a durable handover timestamp, including recovery by GET when
   an acknowledgement response was lost.
4. Execute every nonce starting at zero. Save each complete output leaf and
   verifier quality in SQLite before considering it finished. Build the full
   benchmark Merkle root and send all nonce qualities to the pool.
5. Send proofs for exactly the pool's authoritatively observed sampled nonces.
   Repeat uploads after uncertain HTTP responses; the pool rejects changed
   payloads for the same benchmark.
6. Keep ownership until TIG activation, verification failure or definitive
   expiry. Retain assignment and nonce evidence after freeing the local slot.

SQLite uses WAL and synchronous FULL. A process lock prevents concurrent
writers to one installation. Its directory is bound to the pool origin and
member ID, and must be backed up rather than recreated when updating code.
The runner streams saved solutions, bounds concurrent computations and resumes
only missing nonces. `--drain` finishes existing work without requesting more.
No startup path pulls Git changes, resets configuration or deletes old evidence.
A durable `data/drain.request` also requests draining from a running process.
The [pinned installer](INSTALL_V2.md) preserves the data directory and refuses
an update until the worker has stopped and saved requests are complete.

## Development configuration

Install `requirements-v2.txt` in a separate Python 3.12 environment. The module
entry point is `python3 -m worker_v2 --config /absolute/path/worker.json`.
Provide the execution token through `POOL_V2_EXECUTION_TOKEN`. It cannot move
member funds and is not a TIG API key or wallet signing key.

The JSON configuration requires `pool_origin` (HTTPS), `data_directory`
(separate from legacy files), `resource` (`CPU` or `GPU`), `compute_type`,
`workers` and `runtime_images` (challenge ID to exact image reference). Supported
verification types are `aws_t3`, `aws_t3a`, `aws_t4g`, `aws_c7i`, `aws_c7a`,
`aws_c7g`, `aws_m7i`, `aws_m7a`, `aws_m7g`, and GPU `aws_g4dn`. ARM types require
an ARM host; the other types require AMD64. Use a CPU verification type with
CPU requests and `aws_g4dn` with GPU requests.

Each runtime image must have the form
`ghcr.io/tig-foundation/tig-monorepo/<challenge-name>/runtime@sha256:<digest>`.
Moving tags are rejected. The pool's deployed release manifest supplies
the verified runtime digests for its supported challenges. Optional settings are
`binary_hosts` (default `mainnet-api.tig.foundation` and
`media.githubusercontent.com`) and
`nonce_timeout_seconds` (default 1800).
Optional `runtime_limits` specifies integer `cpu_millis` (1000 = one CPU),
`memory_mib` and `pids_limit`, with optional `cgroup_parent` naming a systemd
slice. All three numeric fields are required when limits are configured.
Memory swap is disabled. Invalid or incomplete limits stop startup before
requesting work. Without this setting, the runtime has no explicit resource
caps; `workers` alone limits nonce concurrency, not CPU or memory consumption.
For a shared machine, use the [bounded local CPU pilot](LOCAL_CPU_PILOT.md),
which also caps the worker and all pilot services together.
The configured pool's hostname is always included so its content-addressed
archive endpoint remains usable for legacy assignments. Explicit older
`binary_hosts` overrides must add `media.githubusercontent.com` before using
direct-download assignments.

New pool assignments supply a direct public TIG/GitHub URL and verified SHA-256.
The worker permits public GET redirects only between allowed HTTPS sources,
restricts GitHub media to TIG's official repository, forwards no credentials,
and verifies the archive before extraction. Extracted libraries are kept under
the worker's `runtime/libraries/<sha256>/` directory and reused by later
assignments with the same checksum, so a stable algorithm is downloaded once
per machine. Pool API requests refuse redirects.
The worker
extracts only expected library/PTX files, and starts containers with its own
deployment and benchmark labels. Libraries are mounted read-only; the results
directory is writable. Runtime containers have no network and do not receive
the execution token or SQLite database. Restart and removal operations check
ownership and never scan or stop legacy containers. Archive filenames use TIG's
algorithm name (such as `titan_killer`), then map to the immutable algorithm ID
within this benchmark's directory.

Direct downloads first deployed in worker `a715041`, paired with pool `f5f1028`
on 13 October. They remain in the currently served worker `dddad9`. The pool stores verified binary metadata for new assignments;
members fetch and verify the archive themselves. The pool's
[lean rollout record](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/LEAN_ROLLOUT_20261013.md)
records activation and storage conversion progress.

## Validation and current limits

Run the suite with the real BLAKE3 dependency installed from `requirements-v2.txt`:

```sh
python3 -m unittest discover -s tests/v2 -v
```

Tests cover CPU/GPU whole assignments, lost responses, interrupted compute,
restart recovery, preserved evidence, runtime isolation and a recorded public
TIG proof. The pool repository also runs this worker against its actual API
using simulated TIG responses and a simulated compute runtime.

Real CPU testnet execution, activation and paired installation passed in
September. The mainnet pool now serves worker `dddad9`, tag
`mainnet-runtime-release-guard-20261014`, paired with pool `59a3446`. The 7–9 October mainnet CPU attempt finished after
the challenge's 120-block lifetime and TIG rejected the results. It is not a
successful mainnet completion check. The pool cleanup records this as expired;
the worker recognizes that terminal state and retains its saved evidence.

The runner currently computes all missing nonces inside one `step()` before
checking the pool again. Its per-nonce timeout is not a whole-benchmark deadline
or a capacity guarantee. On 13 October the intended ARM64 master and helper,
with six workers each, completed all five possible current `c003_a154` CPU
tracks: 12,400 outputs and 15 sampled proofs passed, and the slowest track took
12m33s. An isolated pool API accepted all five result/proof sets and retries.
These checks used simulated TIG acceptance and do not prove a paid completion.
Benchmark viability must be measured again if the algorithm, workload or
hardware changes. GPU execution, interruption during live compute, funded takeover and retention
through settlement remain open. See the pool's
[operations status](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/OPERATIONS_STATUS.md).
Use the pinned v2 installer rather than legacy batch-worker scripts.
