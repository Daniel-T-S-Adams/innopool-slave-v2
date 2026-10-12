# InnoPool v2 member worker

This fork implements whole-benchmark assignments, durable member evidence and
explicit installation of a paired release. The pool's mainnet deployment pins
this fork's commit `fd29279` (tag `mainnet-cpu-pilot-20261007`); new work is
paused following a CPU attempt that expired before TIG accepted its results.
See the pool's [operations status](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/main/docs/OPERATIONS_STATUS.md).
`release/v2`
points at the deployed revision and `main` is the integration branch.

The direct TIG/GitHub binary download update is prepared on
`cleanup/direct-algorithm-downloads`. On 11 October 2026 all 33 v2 tests and
17 inherited regression tests passed locally. On 12 October the optional SSH
member master passed 46 v2 tests and 17 inherited tests. A real SSH/Docker subset
check verified eight knapsack nonces and cached-output recovery on `poolminer1`;
the intended two-server benchmark remains pending SSH access to its helper.
These changes have not been deployed to the production pool or served worker.

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
