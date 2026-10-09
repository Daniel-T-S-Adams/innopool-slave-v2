# InnoPool v2 worker development

This fork implements the whole-benchmark member protocol in the separate
`worker_v2` package. See [the worker guide](WORKER_V2.md) for current behavior,
development configuration and validation limits. The inherited runtime remains
the original batch worker as a historical reference. The mainnet pool
serves pinned v2 worker `fd29279` (`mainnet-cpu-pilot-20261007`); current `main`
is the development branch. See [installation](INSTALL_V2.md) and the pool's
[operations record](https://github.com/Daniel-T-S-Adams/tig-pool-v2/blob/main/docs/OPERATIONS_STATUS.md).
The mainnet CPU attempt expired, so release availability does not establish
successful protocol completion.

## Repository and baseline

- Fork: https://github.com/Daniel-T-S-Adams/innopool-slave-v2
- Upstream: https://github.com/rootztigmod/innopool-slave
- Baseline: `14109c90b38ea342c8264e86ae122b6e9a0e49ea`, tagged `redesign-base`.
- Integration branch: `main` since PR #6 on 8 October 2026; the former
  `redesign/v2` branch is retired. `release/v2` is fast-forwarded to each
  deployed, tested release tag and never receives direct development.
- Features use separate branches and pull requests targeting this fork's
  `main` branch. The baseline tag must not move.

Keep the upstream remote for fetching only. Set `remote.pushDefault` to `origin`
and `remote.upstream.pushurl` to `disabled://upstream-read-only` in development
clones. Do not develop in or push changes to the original repository.

The matching pool repository is
`https://github.com/Daniel-T-S-Adams/tig-pool-v2`. With the owner's approval, it
was created as an independent repository preserving the complete local Git
history because the original remote was inaccessible. The owner subsequently
made it public so the standard GitHub Actions checks could run. Contributors
can read its `POOL_REDESIGN_PLAN.md` and `IMPLEMENTATION_STATUS.md` on the
development branches. The versioned API contract will also live there.
The pool CI pins the worker commit for paired API tests. A production release
must additionally pin and validate both commits with real challenge runtimes.

## Baseline validation

On 20 September 2026, Python 3.12.3 passed all 17 existing regression tests:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

These tests mock runtime and network operations. They do not connect to a live
pool, launch challenge containers, or demonstrate v2 benchmark execution.
The `worker-baseline` CI job repeats them in an isolated runner.

## Installed release workflow and remaining validation

The v2 installer pins a detached commit, isolates its environment/runtime names
and preserves saved evidence during drained updates. The former startup script
now invokes the pinned launcher; it performs no startup Git reset. The README
and [installer guide](INSTALL_V2.md) describe v2; inherited batch-worker behavior
is retained in [the legacy guide](LEGACY_WORKER.md).

CPU testnet execution and activation passed in September. The mainnet attempt
on 7–9 October completed after its protocol lifetime and was rejected. Measure
the whole intended workload on its actual hardware before another paid attempt.
GPU execution, timely mainnet completion and evidence through settlement remain
open checks. Pool cleanup resolves the evidenced late-result attempt as expired
without deleting member evidence or releasing collateral early.
