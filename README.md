# InnoPool v2 member worker

The corrected 14 October mainnet trial activated successfully at TIG height
**1383916**, around **11:35 UTC**. Master/helper saved all 4,000 outputs
(1,968/2,032); results were uploaded **12m40s after handover**.
Confirmed proof and detailed TIG records show no verification failure. All results/proofs match the stored pool
payloads. New work remains paused; reward settlement remains open. The pool
storage ordering fix is deployed. The earlier runtime-pin failure is preserved
in the
[trial record](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/MAINNET_CPU_TRIAL_20261014.md).

The first [14 October mainnet CPU trial](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/MAINNET_CPU_TRIAL_20261014.md)
completed in time but failed solution verification because its knapsack
runtime pin was outdated. The corrected 0.0.8 runtime passed all five unpaid
tracks: 12,400 outputs and 15 sampled proofs, with a slowest track of 12m29s.
Actual uploads and retries passed an isolated pool API replay.

The production pool now serves worker `dddad9` (full commit
`dddad9df9b0d051cf004a904fe7b7361f9816c43`, tag
`mainnet-runtime-release-guard-20261014`), now paired with pool `59a3446` after the 14 October storage fix.
Its runtime release guard checks the pool's digest
and every local/helper runtime map before requesting new work. All 53 v2 and
17 inherited tests passed. Both task-owned member CPU installations use the
corrected worker; original member files remain separate.

This fork implements whole-benchmark assignments, durable member evidence and
explicit paired installation. It downloads algorithm binaries directly from
the verified public TIG/GitHub source and supports a member master with
optional SSH helpers. The 12 October rehearsal also checked disconnect/crash
recovery. Unpaid checks use real runtime/verifier code and simulated pool/TIG
replies. Successful corrected paid activation passed; later settlement remains open;
new work is paused and another paid trial requires fresh approval. See the
pool's [operations status](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/OPERATIONS_STATUS.md).
`release/v2` follows the deployed revision; `main` is the integration branch.
See the [SSH guide](docs/SSH_MEMBER_MASTER_V2.md).

- [Worker behavior and configuration](docs/WORKER_V2.md)
- [Configure a member master and SSH helpers](docs/SSH_MEMBER_MASTER_V2.md)
- [Install, drain and update a pinned worker](docs/INSTALL_V2.md)
- [Preserved baseline and development workflow](docs/REDESIGN.md)

Members may use their own master to coordinate compatible machines and submit
one complete benchmark through the existing pool API. See
[member-managed masters](docs/WORKER_V2.md#member-managed-masters). This reference
worker provides local nonce concurrency and optional SSH helpers. Members
configure and operate the helper machines and their communication, or provide
their own compatible master.

The installer uses `Daniel-T-S-Adams/innopool-slave-v2`, verifies the pool’s
recorded tag and full commit, and creates a separate installation. Restarting
keeps that revision. Updates preserve configuration, credentials and benchmark
evidence, and require existing work to drain first.

Development entry point: `python3 -m worker_v2 --config /absolute/worker.json`.
Install `requirements-v2.txt` in a separate Python 3.12 environment. Execution
tokens authorize work; they cannot authorize a member withdrawal.

The inherited Compose stack is the original batch-worker implementation. Its
instructions are [archived separately](docs/LEGACY_WORKER.md). The fork’s
`scripts/start-fresh.sh` now accepts only a v2 installation directory and starts
its pinned launcher. It does not update Git, recreate containers or install a
legacy service. The original repository and deployment remain separate.
