# Refund Governance Demo

```bash
python examples/refund_agent/main.py
python -m ailuros run list
python -m ailuros run show <run_id>
```

The timeline includes `path_validation_result` after the blocked refund attempt. The refund is still blocked by policy before `payment.issue_refund` executes.
