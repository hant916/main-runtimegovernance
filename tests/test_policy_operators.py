import pytest

from ailuros.models import PolicyOperator
from ailuros.policy import evaluate_operator
from ailuros.utils import MISSING


@pytest.mark.parametrize(
    ("operator", "actual", "expected"),
    [
        (PolicyOperator.EQ, "a", "a"),
        (PolicyOperator.NEQ, "a", "b"),
        (PolicyOperator.GT, 2, 1),
        (PolicyOperator.GTE, 2, 2),
        (PolicyOperator.LT, 1, 2),
        (PolicyOperator.LTE, 2, 2),
        (PolicyOperator.IN, "a", ["a", "b"]),
        (PolicyOperator.NOT_IN, "c", ["a", "b"]),
        (PolicyOperator.EXISTS, None, None),
        (PolicyOperator.NOT_EXISTS, MISSING, None),
        (PolicyOperator.CONTAINS, "hello", "ell"),
        (PolicyOperator.REGEX, "ORD-9231", r"ORD-\d+"),
    ],
)
def test_operator_positive(operator, actual, expected):
    assert evaluate_operator(operator, actual, expected).matched


@pytest.mark.parametrize(
    ("operator", "actual", "expected"),
    [
        (PolicyOperator.EQ, "a", "b"),
        (PolicyOperator.NEQ, "a", "a"),
        (PolicyOperator.GT, 1, 2),
        (PolicyOperator.GTE, 1, 2),
        (PolicyOperator.LT, 2, 1),
        (PolicyOperator.LTE, 2, 1),
        (PolicyOperator.IN, "c", ["a", "b"]),
        (PolicyOperator.NOT_IN, "a", ["a", "b"]),
        (PolicyOperator.EXISTS, MISSING, None),
        (PolicyOperator.NOT_EXISTS, None, None),
        (PolicyOperator.CONTAINS, 1, "x"),
        (PolicyOperator.REGEX, "ORD", "["),
    ],
)
def test_operator_negative(operator, actual, expected):
    assert not evaluate_operator(operator, actual, expected).matched
