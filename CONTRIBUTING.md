# Contributing

Thanks for your interest in the Community Pool member worker.

## Development environment

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-v2.txt
.venv/bin/python -m unittest discover -s tests/v2 -v
```

Python 3.12 is the supported version. The tests mock runtime and network
operations; they do not contact a live pool or start challenge containers. The
`worker-baseline` check in CI runs the same suite.

## Making changes

- Branch from `main` and open a pull request against it. `main` is protected:
  the baseline check must pass and the branch must be up to date.
- The installer's SHA-256 is recorded in the pool's paired-release manifest, so
  any change to `tools/install_worker_v2.py` needs a new paired release on the
  pool side. Call this out in the pull request.
- Evidence durability is the worker's main guarantee: never add a code path
  that deletes saved nonce outputs, assignments or proofs, or that recomputes
  work the member already saved.
- Runtime images must stay pinned by digest; moving tags are refused on
  purpose.
- Add or extend tests next to the code you change and document member-facing
  behaviour in `docs/`.

## Reporting problems

Use GitHub issues for bugs and feature requests. For anything security
related, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
