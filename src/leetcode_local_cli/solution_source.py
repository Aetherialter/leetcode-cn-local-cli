"""Shared decoding boundary for user-authored solution.py files."""

from pathlib import Path


SOLUTION_SOURCE_ENCODING = "utf-8-sig"
INVALID_SOLUTION_ENCODING_MESSAGE = (
    "solution.py 不是有效的 UTF-8 编码，请将文件转换为 UTF-8 后重试"
)


class SolutionSourceEncodingError(ValueError):
    pass


def read_solution_source(path: Path) -> str:
    try:
        return path.read_text(encoding=SOLUTION_SOURCE_ENCODING)
    except UnicodeDecodeError as exc:
        raise SolutionSourceEncodingError(INVALID_SOLUTION_ENCODING_MESSAGE) from exc
