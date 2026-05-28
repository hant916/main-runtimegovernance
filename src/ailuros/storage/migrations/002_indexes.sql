CREATE INDEX IF NOT EXISTS idx_governance_decisions_run_id ON governance_decisions(run_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_run_id ON evaluations(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_reports_run_id ON audit_reports(run_id);
