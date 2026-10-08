# InnoPool v2 member worker

This fork implements whole-benchmark assignments, durable member evidence and
explicit installation of a paired release. The redesign is undergoing
integration; no production v2 release is published yet.

- [Worker behavior and configuration](docs/WORKER_V2.md)
- [Install, drain and update a pinned worker](docs/INSTALL_V2.md)
- [Preserved baseline and development workflow](docs/REDESIGN.md)

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
