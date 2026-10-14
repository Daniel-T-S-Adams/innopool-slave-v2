# InnoPool v2 member worker

The [14 October mainnet CPU trial](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/MAINNET_CPU_TRIAL_20261014.md)
completed in time but exposed an outdated runtime pin. Corrected unpaid checks
are running. This branch adds a check that stops new work when local/helper
runtime images differ from the pool's published requirement; the served worker
remains `a715041` until the corrected pair is activated.

This fork implements whole-benchmark assignments, durable member evidence and
explicit installation of a paired release. The pool's mainnet deployment pins
this fork's commit `a715041` (tag
`mainnet-direct-binaries-member-master-20261013`), paired with pool `f5f1028`.
The pair was activated on 13 October 2026. New work remains paused while
storage cleanup and a separately approved mainnet trial are completed.
See the pool's [operations status](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/cleanup/compact-pool-storage/docs/OPERATIONS_STATUS.md).
`release/v2`
points at the deployed revision and `main` is the integration branch.

The deployed worker downloads binaries directly from the verified public
TIG/GitHub source and supports a member master with optional SSH helpers.
All 46 v2 tests and 17 inherited tests passed. On 13 October the intended
master and helper completed all five possible CPU tracks for `c003_a154`:
12,400 outputs and 15 sampled proofs passed, with a slowest track of 12m33s.
All five result/proof sets also passed an isolated pool API replay. The
12 October rehearsal separately checked disconnect and crash recovery.
These checks used real runtime/verifier code with simulated pool/TIG responses;
successful paid mainnet acceptance and later settlement remain open.
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
