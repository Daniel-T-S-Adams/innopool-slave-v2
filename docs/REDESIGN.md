# InnoPool v2 worker development

This fork implements the whole-benchmark member protocol in the separate
`worker_v2` package. See [the worker guide](WORKER_V2.md) for current behavior,
development configuration and validation limits. The inherited runtime remains
the original batch worker. A tested production v2 release does not exist yet.

## Repository and baseline

- Fork: https://github.com/Daniel-T-S-Adams/innopool-slave-v2
- Upstream: https://github.com/rootztigmod/innopool-slave
- Baseline: `14109c90b38ea342c8264e86ae122b6e9a0e49ea`, tagged `redesign-base`.
- Integration branch: `redesign/v2`; tested releases: `release/v2`.
- Features use separate branches and pull requests targeting this fork's
  `redesign/v2` branch. The baseline tag must not move.

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

## Remaining deployment changes

The v2 installation and release work must replace the inherited startup-time
Git update/reset behavior, isolate services and runtime container names, and
pin the tested worker and pool commits together. Existing README installation
instructions and scripts still describe the legacy worker and are not v2
deployment instructions.
