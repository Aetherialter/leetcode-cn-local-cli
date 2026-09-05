"""Safe parsing primitives for ``lc test`` parameter input."""

import ast
import math
from collections.abc import Mapping
from typing import Any


class LocalTestInputError(ValueError):
    """The user-entered parameter assignments are not supported literals."""


def parse_parameter_assignments(raw: str) -> dict[str, object]:
    """Parse ``name = literal, other = literal`` without executing input.

    The wrapper is parsed only as an AST call.  Every value is then processed
    with ``ast.literal_eval``; calls, names, operators, comprehensions, and
    unpacking are rejected before any user-provided expression can run.
    """
    if raw.strip() == "()":
        return {}
    try:
        expression = ast.parse(f"_lc_test_input({raw})", mode="eval")
    except SyntaxError as exc:
        raise LocalTestInputError("参数格式无效，请使用 name = value 的形式") from exc

    call = expression.body
    if (
        not isinstance(call, ast.Call)
        or not isinstance(call.func, ast.Name)
        or call.func.id != "_lc_test_input"
    ):
        raise LocalTestInputError("参数格式无效，请使用 name = value 的形式")
    if call.args:
        raise LocalTestInputError("参数必须带名称，例如 nums = [1, 2]")

    arguments: dict[str, object] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise LocalTestInputError("不支持 **kwargs 参数展开")
        if keyword.arg in arguments:
            raise LocalTestInputError(f"参数 {keyword.arg} 重复出现")
        try:
            value = ast.literal_eval(keyword.value)
        except (ValueError, TypeError) as exc:
            raise LocalTestInputError(
                f"参数 {keyword.arg} 必须是安全 Python 字面量"
            ) from exc
        _validate_supported_literal(value, parameter_name=keyword.arg)
        arguments[keyword.arg] = value

    if not arguments:
        raise LocalTestInputError("请至少输入一个 name = value 参数")
    return arguments


def encode_arguments(arguments: Mapping[str, object]) -> dict[str, object]:
    """Convert safe literals into the worker's JSON-only protocol values."""
    return {name: _encode_value(value) for name, value in arguments.items()}


def decode_arguments(arguments: object) -> dict[str, object] | None:
    """Decode a worker protocol payload without trusting arbitrary JSON."""
    if not isinstance(arguments, dict) or not all(
        isinstance(name, str) for name in arguments
    ):
        return None
    try:
        return {name: _decode_value(value) for name, value in arguments.items()}
    except (LocalTestInputError, TypeError):
        return None


def _validate_supported_literal(value: object, *, parameter_name: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_supported_literal(item, parameter_name=parameter_name)
        return
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_supported_literal(key, parameter_name=parameter_name)
            _validate_supported_literal(item, parameter_name=parameter_name)
        return
    raise LocalTestInputError(
        f"参数 {parameter_name} 包含不支持的类型；当前支持数字、字符串、列表、字典、元组、True、False 和 None"
    )


def _encode_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if isinstance(value, tuple):
        return {
            "__lc_type__": "tuple",
            "items": [_encode_value(item) for item in value],
        }
    if isinstance(value, dict):
        return {
            "__lc_type__": "dict",
            "items": [
                [_encode_value(key), _encode_value(item)] for key, item in value.items()
            ],
        }
    raise AssertionError("unsupported literals must be rejected before encoding")


def _decode_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if not isinstance(value, dict):
        raise LocalTestInputError("worker value is invalid")
    value_type = value.get("__lc_type__")
    items = value.get("items")
    if value_type == "tuple" and isinstance(items, list):
        return tuple(_decode_value(item) for item in items)
    if value_type == "dict" and isinstance(items, list):
        decoded: dict[Any, object] = {}
        for item in items:
            if not isinstance(item, list) or len(item) != 2:
                raise LocalTestInputError("worker dictionary value is invalid")
            decoded[_decode_value(item[0])] = _decode_value(item[1])
        return decoded
    raise LocalTestInputError("worker value is invalid")
