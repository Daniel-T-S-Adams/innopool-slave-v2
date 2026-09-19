# innopool-slave

InnoPool’s custom TIG benchmarker slave: stock protocol, live telemetry, fast
re-poll, and a local status dashboard.

```bash
git clone https://github.com/rootztigmod/innopool-slave.git
cd innopool-slave
cp .env.example .env
# edit .env — at least SLAVE_NAME, NUM_WORKERS
mkdir -p data/algorithms data/results data/audit
docker compose up -d --build
```

A plain `docker compose up` starts the slave plus CPU runtimes only. GPU
runtimes use the `gpu` profile and need the NVIDIA toolkit.

Dashboard: [http://localhost:8787](http://localhost:8787)  
(Change `DASHBOARD_HOST_PORT` in `.env` if that port is taken.)

## What you get

| Piece | Purpose |
|---|---|
| `slave` | Custom worker (`main.py`) + dashboard on `:8787` |
| Challenge runtimes | `satisfiability`, `vehicle_routing`, `knapsack`, `job_scheduling`, `energy_arbitrage` |
| Telemetry | Sent on every `/get-batches` (see `TELEMETRY.md`) |
| Audit archive | `data/audit/<batch>/leaves.json.gz` — every leaf of every finished batch, kept `AUDIT_TTL` (14 d) |

CPU challenges match the typical InnoPool `pool-cpu-*` route (`c001/c002/c003/c007/c008`).

GPU challenges (`vector_search`, `hypergraph`, `neuralnet_optimizer`) are in the same
compose file under the `gpu` profile. Join-page `install.sh` starts the right set.

```bash
# CPU only (default — no NVIDIA runtime)
docker compose up -d --build

# GPU only (needs NVIDIA Container Toolkit)
docker compose --profile gpu up -d --build slave vector_search hypergraph neuralnet_optimizer
```

Prefer the pool Join-page one-liner over manual clone when onboarding members.

## `.env` checklist

1. **`SLAVE_NAME`** — unique; must be allowed by the pool (e.g. `pool-cpu-<something>`).
2. **`MASTER_IP` / `MASTER_PORT`** — InnoPool master (defaults to `master.innopool.co.uk:80`).
3. **`NUM_WORKERS`** — roughly your vCPU count.
4. **`TIG_VERSION`** — TIG runtime image tag (`latest` or a pinned release).
5. **`AUDIT_DIR` / `AUDIT_TTL`** — where the leaf archive lives (`./data/audit`) and how long batches are kept (seconds, default 14 days). Optional; defaults work. Disk use is a few MB per thousand batches.

## Quality audit

When a batch's merkle root is computed, every leaf (`{nonce}.json`) plus the
leaf hashes are written to `AUDIT_DIR/<batch>/leaves.json.gz` and kept
`AUDIT_TTL` (14 days). Two things read that archive:

- **Sample** — after each accepted root the master replies with `audit_nonces`,
  a few nonces it wants to re-score with `tig-verifier`. The slave posts those
  leaves to `/submit-batch-audit/<batch>` on its own thread within seconds.
- **Fetch** — if a nonce is later reported, the master asks for it via an
  `X-Innopool-Audit-Fetch` header on a normal `get-batches` reply. The slave
  answers with the leaf and its merkle branch, which the master checks against
  the root you committed at submit time, so a leaf cannot be altered after the
  fact — and "I no longer have it" is visible too.

Nothing is re-solved; traffic is a few KB per request. Unsent pushes are
re-queued after a restart. Keep `AUDIT_DIR`: it is your proof the posted
quality was what your machine actually produced.

## Updating

**Installed from the Join page?** Re-run the same one-liner you installed with.
It pulls this repo into `~/innopool-slave-cpu` / `~/innopool-slave-gpu`, rewrites
`.env` from your fleet token (same slave name), rebuilds, and recreates the
containers. It recomputes `NUM_WORKERS` from your core count, so re-apply any
hand-tuned value afterwards.

**Cloned by hand?** The image is built from this repo, so an update is a pull
and a rebuild. Nothing in `.env` needs to change; new settings have defaults.

```bash
cd innopool-slave-cpu   # or innopool-slave / innopool-slave-gpu
git pull
sudo docker compose up -d --build slave                   # CPU
# sudo docker compose --profile gpu up -d --build slave   # GPU
sudo docker compose logs -f slave                         # "Slave Version: 0.1.23"
```

Work in flight is lost when the slave container restarts, so do it between
batches if you can. The challenge runtimes keep running and do not need a rebuild.

## Useful commands

```bash
# All CPU services + slave
docker compose up -d --build

# Logs
docker compose logs -f slave

# Stop
docker compose down
```

Set `VERBOSE=1` in `.env` and recreate the slave for per-nonce debug logs.

## Utilization recorder (optional)

```bash
python3 record_util.py --hours 3 --interval 10
```

Writes `util_logs/util_*.jsonl` next to the compose project when run from this directory (requires the slave containers to be running).

## Drop-in mode (advanced)

If you already run stock `tig-benchmarker`, you can still copy `main.py` + `dashboard/` into `tig-benchmarker/slave/` instead of using this compose file. Prefer this repo’s `docker compose` flow for new installs.

## Version

See `VERSION` (currently `0.1.23`). Reported to the master as `innopool-slave/<VERSION>` from the packaged file — no `.env` override.

After a host crash, do not let Docker auto-start the old containers. Challenge
runtimes use `restart: "no"`. `scripts/start-fresh.sh` pulls images and
force-recreates, then starts work. Join-page `install.sh` installs a systemd
unit that runs that script on boot.

Stopping a batch kills `tig-runtime` / `tig-verifier` inside the challenge
container (not just the host `docker exec` client). Leftover drain matches
argv0 only, so the inspector script cannot count as a leftover on a clean
box. Drain does not count as live work and does not SIGKILL a container
that still has a live batch. `/get-batches` is a capped slice — empty
polls keep in-flight work. A non-empty shrink stops leftover **roots**
master already released; in-flight **proofs** stay.

Missing challenge containers wait up to `INNOPOOL_CONTAINER_WAIT_SEC` (default 120s)
so a reboot does not look like a dead box. After that wait the assignment is
released. Master does not quarantine on this error. `start-fresh.sh` starts
challenge containers and waits for their names before starting the slave.
