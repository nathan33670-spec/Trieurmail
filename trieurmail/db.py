"""Cache local SQLite : en-têtes, corps, résultats IA, plans de tri.

Tout ce qui est coûteux (réseau IMAP, appels LLM) est mis en cache ici afin
de ne jamais être recalculé inutilement.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from .mail.models import MailBody, MailHeader, Attachment

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS messages (
    key TEXT PRIMARY KEY, folder TEXT, uidvalidity INTEGER, uid INTEGER, mid TEXT,
    message_id TEXT, subject TEXT, from_name TEXT, from_addr TEXT, to_addrs TEXT, cc_addrs TEXT,
    date INTEGER, seen INTEGER, flagged INTEGER, answered INTEGER, snippet TEXT, size INTEGER,
    has_attachments INTEGER, is_bulk INTEGER, in_reply_to TEXT, refs TEXT, high_importance INTEGER
);
CREATE INDEX IF NOT EXISTS idx_msg_folder_date ON messages(folder, date);
CREATE INDEX IF NOT EXISTS idx_msg_mid ON messages(mid);
CREATE INDEX IF NOT EXISTS idx_msg_from ON messages(from_addr);
CREATE TABLE IF NOT EXISTS folder_state (folder TEXT PRIMARY KEY, uidvalidity INTEGER, synced_at INTEGER);
CREATE TABLE IF NOT EXISTS date_index (
    folder TEXT, uidvalidity INTEGER, uid INTEGER, ts INTEGER, PRIMARY KEY (folder, uid)
);
CREATE TABLE IF NOT EXISTS bodies (mid TEXT PRIMARY KEY, data TEXT, fetched INTEGER);
CREATE TABLE IF NOT EXISTS insights (
    mid TEXT, kind TEXT, sig TEXT, value TEXT, created INTEGER, PRIMARY KEY (mid, kind)
);
CREATE TABLE IF NOT EXISTS llm_cache (hash TEXT PRIMARY KEY, response TEXT, created INTEGER);
CREATE TABLE IF NOT EXISTS sort_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, created INTEGER, data TEXT);
CREATE TABLE IF NOT EXISTS rules (sender TEXT PRIMARY KEY, folder TEXT, created INTEGER);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""

MSG_COLUMNS = [
    "key", "folder", "uidvalidity", "uid", "mid", "message_id", "subject", "from_name", "from_addr",
    "to_addrs", "cc_addrs", "date", "seen", "flagged", "answered", "snippet", "size", "has_attachments",
    "is_bulk", "in_reply_to", "refs", "high_importance",
]


def _row_to_header(row: sqlite3.Row) -> MailHeader:
    return MailHeader(
        folder=row["folder"], uidvalidity=row["uidvalidity"], uid=row["uid"], message_id=row["message_id"],
        subject=row["subject"], from_name=row["from_name"], from_addr=row["from_addr"],
        to_addrs=row["to_addrs"], cc_addrs=row["cc_addrs"], date=row["date"], seen=bool(row["seen"]),
        flagged=bool(row["flagged"]), answered=bool(row["answered"]), snippet=row["snippet"],
        size=row["size"], has_attachments=bool(row["has_attachments"]), is_bulk=bool(row["is_bulk"]),
        in_reply_to=row["in_reply_to"], references=row["refs"], high_importance=bool(row["high_importance"]),
    )


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    def executemany(self, sql: str, rows: Iterable[Iterable[Any]]) -> None:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany(sql, rows)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    # -- messages ----------------------------------------------------------
    def folder_uidvalidity(self, folder: str) -> Optional[int]:
        rows = self.execute("SELECT uidvalidity FROM folder_state WHERE folder=?", (folder,))
        return rows[0]["uidvalidity"] if rows else None

    def reset_folder(self, folder: str, uidvalidity: int) -> None:
        """UIDVALIDITY a changé : les uids en cache ne sont plus fiables."""
        self.execute("DELETE FROM messages WHERE folder=?", (folder,))
        self.execute("DELETE FROM date_index WHERE folder=?", (folder,))
        self.execute(
            "INSERT OR REPLACE INTO folder_state(folder, uidvalidity, synced_at) VALUES (?,?,?)",
            (folder, uidvalidity, int(time.time())),
        )

    def touch_folder(self, folder: str, uidvalidity: int) -> None:
        self.execute(
            "INSERT OR REPLACE INTO folder_state(folder, uidvalidity, synced_at) VALUES (?,?,?)",
            (folder, uidvalidity, int(time.time())),
        )

    def known_uids(self, folder: str) -> set[int]:
        return {r["uid"] for r in self.execute("SELECT uid FROM messages WHERE folder=?", (folder,))}

    def upsert_headers(self, headers: list[MailHeader]) -> None:
        if not headers:
            return
        placeholders = ",".join("?" * len(MSG_COLUMNS))
        rows = [
            (h.key, h.folder, h.uidvalidity, h.uid, h.mid, h.message_id, h.subject, h.from_name, h.from_addr,
             h.to_addrs, h.cc_addrs, h.date, int(h.seen), int(h.flagged), int(h.answered), h.snippet, h.size,
             int(h.has_attachments), int(h.is_bulk), h.in_reply_to, h.references, int(h.high_importance))
            for h in headers
        ]
        self.executemany(f"INSERT OR REPLACE INTO messages({','.join(MSG_COLUMNS)}) VALUES ({placeholders})", rows)

    def update_flags(self, folder: str, flags: dict[int, tuple[bool, bool, bool]]) -> None:
        self.executemany(
            "UPDATE messages SET seen=?, flagged=?, answered=COALESCE(?, answered) WHERE folder=? AND uid=?",
            [(int(s), int(f), None if a is None else int(a), folder, uid) for uid, (s, f, a) in flags.items()],
        )

    def delete_uids(self, folder: str, uids: Iterable[int]) -> None:
        self.executemany("DELETE FROM messages WHERE folder=? AND uid=?", [(folder, u) for u in uids])

    def forget_moved(self, folder: str, uids: Iterable[int]) -> None:
        """Après un déplacement : l'email sera re-synchronisé dans son nouveau dossier."""
        rows = [(folder, u) for u in uids]
        self.executemany("DELETE FROM messages WHERE folder=? AND uid=?", rows)
        self.executemany("DELETE FROM date_index WHERE folder=? AND uid=?", rows)

    def set_seen(self, keys: list[str], seen: bool) -> None:
        self.executemany("UPDATE messages SET seen=? WHERE key=?", [(int(seen), k) for k in keys])

    def get_header(self, key: str) -> Optional[MailHeader]:
        rows = self.execute("SELECT * FROM messages WHERE key=?", (key,))
        return _row_to_header(rows[0]) if rows else None

    def get_headers(self, keys: list[str]) -> list[MailHeader]:
        out: list[MailHeader] = []
        for i in range(0, len(keys), 500):
            chunk = keys[i : i + 500]
            rows = self.execute(f"SELECT * FROM messages WHERE key IN ({','.join('?' * len(chunk))})", chunk)
            out.extend(_row_to_header(r) for r in rows)
        order = {k: i for i, k in enumerate(keys)}
        out.sort(key=lambda h: order.get(h.key, 0))
        return out

    def query_headers(
        self,
        folders: list[str],
        since_ts: Optional[int] = None,
        until_ts: Optional[int] = None,
        unseen_only: bool = False,
        search: str = "",
        limit: int = 100000,
        offset: int = 0,
    ) -> tuple[list[MailHeader], int]:
        if not folders:
            return [], 0
        where = [f"folder IN ({','.join('?' * len(folders))})"]
        params: list[Any] = list(folders)
        if since_ts is not None:
            where.append("date >= ?")
            params.append(since_ts)
        if until_ts is not None:
            where.append("date < ?")
            params.append(until_ts)
        if unseen_only:
            where.append("seen = 0")
        if search:
            where.append("(subject LIKE ? OR from_name LIKE ? OR from_addr LIKE ? OR snippet LIKE ?)")
            like = f"%{search}%"
            params += [like] * 4
        clause = " AND ".join(where)
        total = self.execute(f"SELECT COUNT(*) AS n FROM messages WHERE {clause}", params)[0]["n"]
        rows = self.execute(
            f"SELECT * FROM messages WHERE {clause} ORDER BY date DESC LIMIT ? OFFSET ?", params + [limit, offset]
        )
        return [_row_to_header(r) for r in rows], total

    # -- timeline ----------------------------------------------------------
    def date_index_max_uid(self, folder: str) -> int:
        rows = self.execute(
            "SELECT MAX(uid) AS m FROM date_index WHERE folder=? AND typeof(uid)='integer'", (folder,)
        )
        return rows[0]["m"] or 0

    def date_index_max_ts(self, folder: str) -> int:
        rows = self.execute("SELECT MAX(ts) AS m FROM date_index WHERE folder=?", (folder,))
        return rows[0]["m"] or 0

    def add_dates(self, folder: str, uidvalidity: int, items: list[tuple[int, int]]) -> None:
        self.executemany(
            "INSERT OR REPLACE INTO date_index(folder, uidvalidity, uid, ts) VALUES (?,?,?,?)",
            [(folder, uidvalidity, uid, ts) for uid, ts in items],
        )

    def date_index_uidvalidity(self, folder: str) -> Optional[int]:
        rows = self.execute("SELECT uidvalidity FROM date_index WHERE folder=? LIMIT 1", (folder,))
        return rows[0]["uidvalidity"] if rows else None

    def clear_date_index(self, folder: str) -> None:
        self.execute("DELETE FROM date_index WHERE folder=?", (folder,))

    def timestamps(self, folders: list[str]) -> list[int]:
        if not folders:
            return []
        rows = self.execute(
            f"SELECT ts FROM date_index WHERE folder IN ({','.join('?' * len(folders))}) AND ts > 0", folders
        )
        return [r["ts"] for r in rows]

    # -- corps -------------------------------------------------------------
    def get_body(self, mid: str) -> Optional[MailBody]:
        rows = self.execute("SELECT data FROM bodies WHERE mid=?", (mid,))
        if not rows:
            return None
        data = json.loads(rows[0]["data"])
        data["attachments"] = [Attachment(**a) for a in data.get("attachments", [])]
        return MailBody(**data)

    def put_body(self, mid: str, body: MailBody) -> None:
        data = {
            "text": body.text[:200_000],
            "html": body.html[:500_000],
            "attachments": [a.__dict__ for a in body.attachments],
            "headers": body.headers,
        }
        self.execute(
            "INSERT OR REPLACE INTO bodies(mid, data, fetched) VALUES (?,?,?)",
            (mid, json.dumps(data, ensure_ascii=False), int(time.time())),
        )

    # -- résultats IA ------------------------------------------------------
    def get_insights(self, mids: list[str], kind: str, sig: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for i in range(0, len(mids), 500):
            chunk = mids[i : i + 500]
            rows = self.execute(
                f"SELECT mid, value FROM insights WHERE kind=? AND sig=? AND mid IN ({','.join('?' * len(chunk))})",
                [kind, sig, *chunk],
            )
            out.update({r["mid"]: json.loads(r["value"]) for r in rows})
        return out

    def put_insights(self, kind: str, sig: str, values: dict[str, Any]) -> None:
        now = int(time.time())
        self.executemany(
            "INSERT OR REPLACE INTO insights(mid, kind, sig, value, created) VALUES (?,?,?,?,?)",
            [(mid, kind, sig, json.dumps(v, ensure_ascii=False), now) for mid, v in values.items()],
        )

    def any_insights(self, mids: list[str], kind: str) -> dict[str, Any]:
        """Résultats existants quelle que soit la signature (affichage)."""
        out: dict[str, Any] = {}
        for i in range(0, len(mids), 500):
            chunk = mids[i : i + 500]
            rows = self.execute(
                f"SELECT mid, value FROM insights WHERE kind=? AND mid IN ({','.join('?' * len(chunk))})",
                [kind, *chunk],
            )
            out.update({r["mid"]: json.loads(r["value"]) for r in rows})
        return out

    # -- cache LLM ---------------------------------------------------------
    def llm_get(self, h: str) -> Optional[str]:
        rows = self.execute("SELECT response FROM llm_cache WHERE hash=?", (h,))
        return rows[0]["response"] if rows else None

    def llm_put(self, h: str, response: str) -> None:
        self.execute(
            "INSERT OR REPLACE INTO llm_cache(hash, response, created) VALUES (?,?,?)", (h, response, int(time.time()))
        )

    def clear_ai_cache(self) -> None:
        self.execute("DELETE FROM llm_cache")
        self.execute("DELETE FROM insights")

    # -- plans de tri ------------------------------------------------------
    def save_plan(self, data: dict, plan_id: Optional[int] = None) -> int:
        payload = json.dumps(data, ensure_ascii=False)
        if plan_id is None:
            with self._lock:
                cur = self._conn.execute(
                    "INSERT INTO sort_plans(created, data) VALUES (?,?)", (int(time.time()), payload)
                )
                return int(cur.lastrowid)
        self.execute("UPDATE sort_plans SET data=? WHERE id=?", (payload, plan_id))
        return plan_id

    def get_plan(self, plan_id: Optional[int] = None) -> Optional[dict]:
        if plan_id is None:
            rows = self.execute("SELECT id, data FROM sort_plans ORDER BY id DESC LIMIT 1")
        else:
            rows = self.execute("SELECT id, data FROM sort_plans WHERE id=?", (plan_id,))
        if not rows:
            return None
        data = json.loads(rows[0]["data"])
        data["id"] = rows[0]["id"]
        return data

    # -- règles ------------------------------------------------------------
    def save_rules(self, rules: dict[str, str]) -> None:
        now = int(time.time())
        self.executemany(
            "INSERT OR REPLACE INTO rules(sender, folder, created) VALUES (?,?,?)",
            [(s, f, now) for s, f in rules.items()],
        )

    def get_rules(self) -> dict[str, str]:
        return {r["sender"]: r["folder"] for r in self.execute("SELECT sender, folder FROM rules")}

    def delete_rules(self) -> None:
        self.execute("DELETE FROM rules")

    # -- clé/valeur --------------------------------------------------------
    def kv_get(self, key: str, default: Any = None) -> Any:
        rows = self.execute("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def kv_set(self, key: str, value: Any) -> None:
        self.execute("INSERT OR REPLACE INTO kv(key, value) VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def stats(self) -> dict:
        return {
            "messages": self.execute("SELECT COUNT(*) AS n FROM messages")[0]["n"],
            "bodies": self.execute("SELECT COUNT(*) AS n FROM bodies")[0]["n"],
            "insights": self.execute("SELECT COUNT(*) AS n FROM insights")[0]["n"],
            "llm_cache": self.execute("SELECT COUNT(*) AS n FROM llm_cache")[0]["n"],
            "rules": self.execute("SELECT COUNT(*) AS n FROM rules")[0]["n"],
        }
