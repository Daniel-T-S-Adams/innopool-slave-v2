# InnoPool v2 worker development

This fork will implement the whole-benchmark member protocol described in the
pool redesign plan. The existing runtime remains the original batch worker;
the v2 worker and a tested v2 release do not exist yet.

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

The matching pool destination is
`https://github.com/Daniel-T-S-Adams/tig-pool-v2`. Creating that fork is currently
blocked because the authenticated account cannot access `rootztigmod/tig-pool`.
The maintained plan and versioned API contract will live in the pool fork once
it is established. Paired pool/worker commit checks must be added before any
v2 release; the current worker-only CI does not establish v2 compatibility.

## Baseline validation

On 20 September 2026, Python 3.12.3 passed all 17 existing regression tests:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

These tests mock runtime and network operations. They do not connect to a live
pool, launch challenge containers, or demonstrate v2 benchmark execution.
The `worker-baseline` CI job repeats them in an isolated runner.

## Planned changes

The reference runner will request either CPU or GPU work, persist a complete
benchmark assignment, acknowledge receipt before execution, and recover that
confirmation after lost responses or restarts. It will deliver the full
benchmark result and requested proofs, retain evidence through settlement,
and never give another member ownership of existing work.

The v2 installation and release work must replace the inherited startup-time
Git update/reset behavior, isolate services and runtime container names, and
pin the tested worker and pool commits together. Existing README installation
instructions and scripts still describe the legacy worker and are not v2
deployment instructions.
