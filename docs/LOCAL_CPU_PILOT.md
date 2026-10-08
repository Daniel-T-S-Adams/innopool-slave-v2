# CPU-only pilot on a shared machine

This initial pilot uses one existing Linux host and one member worker at a
time. Member A and Member B take turns with separate installations and saved
evidence. GPU execution and testing on separate machines remain later checks.
These resource controls do not publish a paired release, deploy a pool, fund
members, or authorize benchmark submissions.

## Shared budget

The supplied `deploy/local-cpu-pilot/innopoolv2pilot.slice` imposes one aggregate
budget on all pilot services and their Docker runtimes:

| Resource | Ceiling |
|---|---|
| Combined CPU | One core's worth of processing time; low scheduling weight |
| Combined memory | 2 GiB hard maximum; reclaim begins at 1792 MiB |
| Combined swap | None |
| Combined processes/threads | 256 |
| One benchmark runtime | One CPU, 1280 MiB, no swap, 128 processes/threads |
| Active member workers | One; one nonce computed at a time |

The remaining part of the shared memory budget accommodates the worker,
database, API and collectors. It is not reserved from other host applications.
The launcher checks available RAM before starting, allowing for the slice's
unused budget plus at least 1 GiB of host headroom, and requires 10 GiB of free
disk. Other applications may change their own resource use afterwards. Disk
space and host memory still need monitoring during a live pilot.

Docker containers must explicitly join this slice: restricting only the Python
worker does not restrict containers created by the Docker daemon. Every new
pilot database/API/collector service must also use `Slice=innopoolv2pilot.slice`
or Docker's `--cgroup-parent=innopoolv2pilot.slice`. Existing unrelated services
are outside this pilot. A pre-existing development test database is not a live
funds database and is not included merely by starting this slice.

## Prepare the host

Requires Linux cgroup v2, systemd and local Docker with the systemd cgroup driver.
Review the unit before installing it, and do not overwrite a different existing
unit of the same name. From the worker checkout, as the host operator:

```sh
systemd-analyze verify deploy/local-cpu-pilot/innopoolv2pilot.slice
install -m 0644 deploy/local-cpu-pilot/innopoolv2pilot.slice /etc/systemd/system/innopoolv2pilot.slice
systemctl daemon-reload
systemctl start innopoolv2pilot.slice
python3 tools/run_cpu_pilot.py --check
```

The slice alone performs no computation. After a reboot, start it and rerun the
check before launching the pilot; future service units must declare their slice.
Do not stop the slice while work or observers are running.

## Prepare each worker

Once the pool's tested paired release and member tokens are available, follow
[the installer procedure](INSTALL_V2.md) into separate private directories, for
example `/var/lib/innopool-v2-pilot/member-a` and `member-b`. Offer CPU only with
`--workers 1` and a verification type compatible with the machine's architecture.
On the current ARM64 host use a supported ARM verification type; AMD64 and GPU
types are unsuitable.

Before the first launch, add this object to each installation's `worker.json`,
leaving its release, pool, identity and data-directory settings intact:

```json
"runtime_limits": {
  "cpu_millis": 1000,
  "memory_mib": 1280,
  "pids_limit": 128,
  "cgroup_parent": "innopoolv2pilot.slice"
}
```

`cpu_millis=1000` means one CPU. The worker validates the limits before requesting
work and verifies that its own process is inside the bounded slice. The installer
preserves this configuration on drained updates. Containers receive the limits
when created. Recovery checks existing owned containers and recreates one if its
limits or placement differ, retaining all bind-mounted results and worker state.
Containers belonging to another installation are never removed.

## Start, drain and switch members

From the tested worker checkout, as the host operator:

```sh
python3 tools/run_cpu_pilot.py /var/lib/innopool-v2-pilot/member-a --check
python3 tools/run_cpu_pilot.py /var/lib/innopool-v2-pilot/member-a
```

The launcher verifies the shared budget and worker configuration, selects the
local Docker daemon, then runs the pinned installation as the fixed
`innopoolv2pilot-worker.service` unit. Starting a second worker while this unit
exists is refused by systemd. It also supplies `--require-resource-limits`, so
older worker releases that lack this option stop rather than ignore the new
configuration. Logs are available using
`journalctl -u innopoolv2pilot-worker.service`. Do not launch the worker's `run`
file directly from an ordinary shell: the required shared slice would be absent.

To finish existing work before switching to Member B, request a drain using
the downloaded installer and wait for the service to exit successfully:

```sh
python3 install_worker_v2.py drain --directory /var/lib/innopool-v2-pilot/member-a
python3 tools/run_cpu_pilot.py /var/lib/innopool-v2-pilot/member-b
```

After a crash, restart the same installation with the launcher's `--drain` flag
to recover existing work without requesting another benchmark. Retain its
evidence. Do not switch away from unresolved work or clear state to force a new
request. A failed service does not automatically restart or request new work.

## Before funded execution

Check an actual CPU algorithm's memory and running time under these same limits
without submitting paid work. Hard limits protect the host by throttling or
killing an oversized workload; that workload may therefore fail or miss its TIG
deadline. Failure after handover can forfeit collateral under the agreed rules.
If it does not fit, use a larger test host or revisit the test scope before
funding; do not silently relax these limits.

The pool must enforce the separately recorded financial/benchmark-count limits.
One worker can otherwise request another benchmark after finishing the first.
The production deployment, account validation and monitoring checks remain
required before enabling live work. CPU-only tests do not demonstrate GPU
execution, independent-host recovery or a positive protocol reward payment.

Resource flag semantics: [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)
and [Docker container run](https://docs.docker.com/reference/cli/docker/container/run/).
