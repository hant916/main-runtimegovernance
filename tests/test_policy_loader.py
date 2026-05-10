import pytest

from ailuros.policy import PolicyLoader, PolicyValidationError


def test_policy_loader_valid_file():
    policy = PolicyLoader().load_file("tests/policy/fixtures/valid_refund_policy.json")

    assert policy.policy_id == "refund.high_value_requires_review"


def test_policy_loader_invalid_files():
    loader = PolicyLoader()

    with pytest.raises(PolicyValidationError, match="missing required field: policy_id"):
        loader.load_file("tests/policy/fixtures/invalid_missing_id.json")
    with pytest.raises(PolicyValidationError, match="unknown operator"):
        loader.load_file("tests/policy/fixtures/invalid_unknown_operator.json")


def test_policy_loader_directory():
    policies = PolicyLoader().load_directory("tests/policy/fixtures")

    assert any(policy.policy_id == "refund.high_value_requires_review" for policy in policies)
