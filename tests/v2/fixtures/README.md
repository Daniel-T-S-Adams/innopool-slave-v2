# Public TIG proof fixture

`tig-proof.json.gz` contains one complete Merkle proof, its actual root and
49,000-nonce benchmark size from public benchmark
`0017d114eead779d2a14567929f45c69`, retrieved on 20 September 2026 from
[TIG's benchmark data endpoint](https://mainnet-api.tig.foundation/get-benchmark-data?benchmark_id=0017d114eead779d2a14567929f45c69).
It preserves the returned solution string and metadata without modification.
The other sampled proofs and unrelated response fields were omitted to keep
the fixture small. The gzip SHA-256 is
`c77aadd84f06c95c45d6f4ddb4c13fe3ad4bfa2fff6f66d2fdf6be20670159c9`.

The test checks the worker's serialization, solution signature, leaf hashing
and encoded branch against the root published by TIG. Synthetic odd-sized
trees separately cover generation of complete proofs. Neither test runs an
algorithm or submits work to TIG.
