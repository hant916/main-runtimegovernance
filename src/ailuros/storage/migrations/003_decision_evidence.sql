ALTER TABLE governance_decisions ADD COLUMN risk_level TEXT NOT NULL DEFAULT 'low';
ALTER TABLE governance_decisions ADD COLUMN evidence_refs_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE governance_decisions ADD COLUMN input_hash TEXT;
ALTER TABLE governance_decisions ADD COLUMN tool_name TEXT;
