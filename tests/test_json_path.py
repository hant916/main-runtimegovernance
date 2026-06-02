from ailuros.utils import MISSING, get_by_path


def test_get_by_path_nested_dict_and_missing() -> None:
    data = {"arguments": {"amount_eur": 780, "nullable": None}}

    assert get_by_path(data, "arguments.amount_eur") == 780
    assert get_by_path(data, "arguments.nullable") is None
    assert get_by_path(data, "arguments.missing") is MISSING
