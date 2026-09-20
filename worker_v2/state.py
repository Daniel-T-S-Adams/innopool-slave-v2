"""Durable member-side assignments and evidence, retained across restarts."""

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(payload):
    return hashlib.sha256(payload.encode()).hexdigest()


class StateError(ValueError):
    pass


class NonceResults(Mapping):
    """Stream leaves from SQLite instead of loading every solution into RAM."""
    def __init__(self, connection, benchmark_id):
        self.connection, self.benchmark_id = connection, benchmark_id

    def __len__(self):
        return self.connection.execute("SELECT count(*) FROM nonces WHERE benchmark_id=?", (self.benchmark_id,)).fetchone()[0]

    def __iter__(self):
        return (row[0] for row in self.connection.execute("SELECT nonce FROM nonces WHERE benchmark_id=? ORDER BY nonce", (self.benchmark_id,)))

    def __getitem__(self, nonce):
        row = self.connection.execute("SELECT leaf,quality FROM nonces WHERE benchmark_id=? AND nonce=?", (self.benchmark_id, nonce)).fetchone()
        if row is None:
            raise KeyError(nonce)
        return json.loads(row[0]), row[1]


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / "member-worker.sqlite3"
        self.connection = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise StateError("worker state needs a compatible release")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), origin TEXT NOT NULL, member_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requests (
                request_key TEXT PRIMARY KEY, offer TEXT NOT NULL, server_id TEXT UNIQUE,
                benchmark_id TEXT UNIQUE, finished INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS assignments (
                benchmark_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
                acknowledged_at TEXT, result_sent INTEGER NOT NULL DEFAULT 0,
                proofs_digest TEXT, terminal_state TEXT);
            CREATE TABLE IF NOT EXISTS nonces (
                benchmark_id TEXT NOT NULL REFERENCES assignments, nonce INTEGER NOT NULL,
                leaf TEXT NOT NULL, quality INTEGER NOT NULL,
                PRIMARY KEY(benchmark_id,nonce));
            PRAGMA user_version=1;
        """)

    def close(self):
        self.connection.close()

    def bind(self, origin, member_id):
        with self.connection:
            row = self.connection.execute("SELECT origin,member_id FROM identity").fetchone()
            if row and tuple(row) != (origin, member_id):
                raise StateError("this evidence directory belongs to another pool or member")
            self.connection.execute("INSERT OR IGNORE INTO identity VALUES (1,?,?)", (origin, member_id))

    def request(self, offer):
        row = self.connection.execute("SELECT * FROM requests WHERE finished=0 ORDER BY rowid LIMIT 1").fetchone()
        if row:
            return dict(row)
        key = str(uuid.uuid4())
        with self.connection:
            self.connection.execute("INSERT INTO requests(request_key,offer) VALUES (?,?)", (key, canonical(offer)))
        return {"request_key": key, "offer": canonical(offer), "server_id": None, "benchmark_id": None, "finished": 0}

    def unfinished(self):
        row = self.connection.execute("SELECT * FROM requests WHERE finished=0 ORDER BY rowid LIMIT 1").fetchone()
        return dict(row) if row else None

    def link_request(self, key, server_id, benchmark_id=None):
        with self.connection:
            row = self.connection.execute("SELECT server_id,benchmark_id FROM requests WHERE request_key=?", (key,)).fetchone()
            if not row or (row["server_id"] and row["server_id"] != server_id) or (
                    row["benchmark_id"] and benchmark_id and row["benchmark_id"] != benchmark_id):
                raise StateError("work request identity changed")
            self.connection.execute("UPDATE requests SET server_id=?,benchmark_id=coalesce(benchmark_id,?) WHERE request_key=?",
                                    (server_id, benchmark_id, key))

    def save_assignment(self, benchmark_id, payload, expected_digest):
        if not isinstance(payload, str) or digest(payload) != expected_digest:
            raise StateError("complete assignment digest does not match its payload bytes")
        assignment = json.loads(payload)
        if assignment.get("benchmark_id") != benchmark_id or assignment.get("api_version") != "2.0":
            raise StateError("assignment identity or version is incompatible")
        with self.connection:
            row = self.connection.execute("SELECT payload,digest FROM assignments WHERE benchmark_id=?", (benchmark_id,)).fetchone()
            if row and tuple(row) != (payload, expected_digest):
                raise StateError("immutable benchmark assignment changed")
            self.connection.execute("INSERT OR IGNORE INTO assignments(benchmark_id,payload,digest) VALUES (?,?,?)",
                                    (benchmark_id, payload, expected_digest))
        return assignment

    def assignment(self, benchmark_id):
        row = self.connection.execute("SELECT * FROM assignments WHERE benchmark_id=?", (benchmark_id,)).fetchone()
        if not row:
            raise StateError("assignment was not saved")
        return dict(row)

    def acknowledge(self, benchmark_id, timestamp):
        if not isinstance(timestamp, str) or not timestamp:
            raise StateError("pool did not confirm durable handover")
        with self.connection:
            row = self.assignment(benchmark_id)
            if row["acknowledged_at"] and row["acknowledged_at"] != timestamp:
                raise StateError("confirmed handover timestamp changed")
            self.connection.execute("UPDATE assignments SET acknowledged_at=? WHERE benchmark_id=?", (timestamp, benchmark_id))

    def save_nonce(self, benchmark_id, nonce, leaf, quality):
        if not self.assignment(benchmark_id)["acknowledged_at"]:
            raise StateError("work cannot run before confirmed handover")
        if type(nonce) is not int or nonce < 0 or leaf.get("nonce") != nonce:
            raise StateError("runtime returned the wrong nonce")
        if type(quality) is not int or not -(2**31) <= quality < 2**31:
            raise StateError("runtime quality must fit the protocol int32 range")
        encoded = canonical(leaf)
        with self.connection:
            row = self.connection.execute("SELECT leaf,quality FROM nonces WHERE benchmark_id=? AND nonce=?", (benchmark_id, nonce)).fetchone()
            if row and tuple(row) != (encoded, quality):
                raise StateError("saved nonce evidence differs from a repeated computation")
            self.connection.execute("INSERT OR IGNORE INTO nonces VALUES (?,?,?,?)", (benchmark_id, nonce, encoded, quality))

    def nonces(self, benchmark_id):
        return NonceResults(self.connection, benchmark_id)

    def result_sent(self, benchmark_id):
        with self.connection:
            self.connection.execute("UPDATE assignments SET result_sent=1 WHERE benchmark_id=?", (benchmark_id,))

    def proofs_sent(self, benchmark_id, proof_digest):
        with self.connection:
            self.connection.execute("UPDATE assignments SET proofs_digest=? WHERE benchmark_id=?", (proof_digest, benchmark_id))

    def finish(self, request_key, state):
        with self.connection:
            self.connection.execute("UPDATE requests SET finished=1 WHERE request_key=?", (request_key,))
            self.connection.execute("UPDATE assignments SET terminal_state=? WHERE benchmark_id=(SELECT benchmark_id FROM requests WHERE request_key=?)",
                                    (state, request_key))
        # Evidence remains present through arbitration/finalization. This module
        # has no time-based deletion and never inherits legacy AUDIT_TTL cleanup.
