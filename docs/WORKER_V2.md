# Whole-benchmark reference worker

`worker_v2` implements member API version `2.0`. It runs independently of the
legacy worker and owns one entire benchmark at a time. Members may run their
own compatible clients or multiple installations; the pool enforces the shared
two-slot limit for each member across CPU and GPU requests.

## Member-managed masters

Members may replace this reference client with a master that distributes nonce
computation across their own compatible machines. The master uses the same
API 2.0 work request, assignment, acknowledgement, complete result and proof
routes. It remains responsible for the whole benchmark after confirmed handover.
Members implement internal transport, scheduling, recovery and output aggregation.
The pool's [member master contract](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/main/docs/MEMBER_MASTER_V2.md)
specifies that integration. Paired pool tests exercise a simulated master
combining helper outputs, recovering missing work after restart, and submitting
one complete result and sampled proofs. Remote helper transport and timely
execution on the intended hardware remain unverified. These changes are not deployed.

Every helper used for an assignment must match its verification compute type
and compatible architecture, algorithm binary and runtime. A custom master may
offer aggregate concurrent nonce capacity across compatible machines. It must
save complete outputs durably, return one whole-benchmark root with all nonce
qualities in order, and supply exactly TIG's sampled proofs. Keep execution
credentials with the pool-facing master; helpers do not need pool credentials.

This reference implementation executes on one machine. Its `workers` setting
controls local concurrent nonce computations and does not connect other machines.
Running several independent installations requests separate benchmarks; all
installations still share the member's two-slot limit. Sharing one benchmark
requires a member-managed master to aggregate the outputs before upload.
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
and verifies the archive before extraction. Pool API requests refuse redirects.
The worker
extracts only expected library/PTX files, and starts containers with its own
deployment and benchmark labels. Libraries are mounted read-only; the results
directory is writable. Runtime containers have no network and do not receive
the execution token or SQLite database. Restart and removal operations check
ownership and never scan or stop legacy containers. Archive filenames use TIG's
algorithm name (such as `titan_killer`), then map to the immutable algorithm ID
within this benchmark's directory.

The direct-download changes are implemented on the storage cleanup branch,
without runtime tests or deployment. Mainnet still serves worker `fd29279`.
The pool's `docs/LEAN_STORAGE.md` records the implementation and activation
sequence.

## Validation and current limits

Run the legacy and v2 suites in separate processes: the legacy tests install
mock modules that must not replace the real BLAKE3 dependency in v2 tests.

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s tests/v2 -v
```

Tests cover CPU/GPU whole assignments, lost responses, interrupted compute,
restart recovery, preserved evidence, runtime isolation and a recorded public
TIG proof. The pool repository also runs this worker against its actual API
using simulated TIG responses and a simulated compute runtime.

Real CPU testnet execution, activation and paired installation passed in
September. The mainnet pool now serves worker `fd29279`, tag
`mainnet-cpu-pilot-20261007`. The 7–9 October mainnet CPU attempt finished after
the challenge's 120-block lifetime and TIG rejected the results. It is not a
successful mainnet completion check. The pool cleanup records this as expired;
the worker recognizes that terminal state and retains its saved evidence.

The runner currently computes all missing nonces inside one `step()` before
checking the pool again. Its per-nonce timeout is not a whole-benchmark deadline
or a capacity guarantee. Benchmark viability must be measured on the intended
hardware and limits before another paid attempt. GPU execution, timely mainnet
completion, interruption during live compute, funded takeover and retention
through settlement remain open. See the pool's
[operations status](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/main/docs/OPERATIONS_STATUS.md).
Use the pinned v2 installer rather than legacy batch-worker scripts.
