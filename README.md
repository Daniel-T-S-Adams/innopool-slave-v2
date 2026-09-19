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
| Audit copies | `data/audit/<batch>/` — the leaves the master asked to re-check, kept `AUDIT_TTL` (30 d) |

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
5. **`AUDIT_DIR` / `AUDIT_TTL`** — where audit copies live (`./data/audit`) and how long they are kept (seconds, default 30 days). Optional; defaults work.

## Quality audit

After each accepted root the master may reply with `audit_nonces`: a few nonces
it wants to re-score with `tig-verifier`. The slave copies those `{nonce}.json`
files to `AUDIT_DIR`, posts them to `/submit-batch-audit/<batch>` on its own
thread, and re-queues anything unsent after a restart. Nothing is re-solved and
the extra traffic is a few KB per batch.

Keep `AUDIT_DIR`: if TIG ever disputes a benchmark you computed, those files are
your proof the posted quality was what your machine actually produced.

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
sudo docker compose logs -f slave                         # "Slave Version: 0.1.22"
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

See `VERSION` (currently `0.1.22`). Reported to the master as `innopool-slave/<VERSION>` from the packaged file — no `.env` override.

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
