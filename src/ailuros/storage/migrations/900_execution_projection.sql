CREATE TABLE IF NOT EXISTS projections (
  run_id TEXT PRIMARY KEY,
  projection_schema TEXT NOT NULL,
  projection_version TEXT NOT NULL,
  source TEXT NOT NULL,
  lifecycle_status TEXT,
  outcome_summary TEXT,
  validation_summary TEXT,
  projection_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
  signal_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  type TEXT NOT NULL,
  severity TEXT NOT NULL,
  subject TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_run_type ON signals(run_id, type);
