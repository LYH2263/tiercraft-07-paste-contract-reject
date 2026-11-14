from __future__ import annotations

from app.db import connect
from app.services import pipeline


SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  biz_key TEXT NOT NULL,
  fixture_file TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS domain_contracts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  field TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  ftype TEXT NOT NULL,
  UNIQUE(domain_id, field),
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS layer_paste (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  biz_day TEXT NOT NULL,
  store_code TEXT NOT NULL,
  store_name TEXT NOT NULL,
  category TEXT NOT NULL,
  amount REAL NOT NULL,
  qty INTEGER NOT NULL,
  raw_json TEXT NOT NULL,
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS paste_rejects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  job_id INTEGER,
  line_no INTEGER NOT NULL,
  raw_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS layer_detail (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  biz_day TEXT NOT NULL,
  store_code TEXT NOT NULL,
  store_name TEXT NOT NULL,
  category TEXT NOT NULL,
  amount REAL NOT NULL,
  qty INTEGER NOT NULL,
  clean_flag TEXT NOT NULL,
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS layer_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  biz_day TEXT NOT NULL,
  store_code TEXT NOT NULL,
  amount_sum REAL NOT NULL,
  qty_sum INTEGER NOT NULL,
  line_count INTEGER NOT NULL,
  UNIQUE(domain_id, biz_day, store_code),
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS layer_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  step TEXT NOT NULL,
  status TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  in_count INTEGER NOT NULL DEFAULT 0,
  out_count INTEGER NOT NULL DEFAULT 0,
  drop_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS reconcile_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL,
  paste_count INTEGER NOT NULL,
  detail_count INTEGER NOT NULL,
  summary_line_sum INTEGER NOT NULL,
  key_mismatch INTEGER NOT NULL,
  amount_drift REAL NOT NULL,
  status TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(domain_id) REFERENCES domains(id)
);
"""


def init_db() -> None:
    conn = connect()
    domain_ids: list[int] = []
    try:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT COUNT(*) AS c FROM domains").fetchone()
        if int(row["c"]) == 0:
            _seed_domain(conn)
        _ensure_contracts(conn)
        conn.commit()
        # 没有贴源装载任务记录的主题域（含旧库直装迁移）补跑一次契约装载
        rows = conn.execute(
            """
            SELECT d.id AS id FROM domains d
            WHERE NOT EXISTS (
              SELECT 1 FROM layer_jobs j WHERE j.domain_id = d.id AND j.step = 'load_paste'
            )
            ORDER BY d.id
            """
        ).fetchall()
        domain_ids = [int(r["id"]) for r in rows]
    finally:
        conn.close()
    for domain_id in domain_ids:
        pipeline.run_load_paste(domain_id)


def _seed_domain(conn) -> None:
    conn.execute(
        """
        INSERT INTO domains(name, biz_key, fixture_file, description)
        VALUES (?, ?, ?, ?)
        """,
        (
            "门店日销售",
            "业务日+门店编码",
            "门店日销售-贴源.jsonl",
            "演示贴源装载、明细清洗与按门店日汇总",
        ),
    )


def _ensure_contracts(conn) -> None:
    rows = conn.execute(
        """
        SELECT d.id AS id FROM domains d
        WHERE NOT EXISTS (SELECT 1 FROM domain_contracts c WHERE c.domain_id = d.id)
        ORDER BY d.id
        """
    ).fetchall()
    for row in rows:
        for item in pipeline.DEFAULT_CONTRACT:
            conn.execute(
                """
                INSERT INTO domain_contracts(domain_id, field, required, ftype)
                VALUES (?, ?, ?, ?)
                """,
                (int(row["id"]), item["field"], item["required"], item["ftype"]),
            )
