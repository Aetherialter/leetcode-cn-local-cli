import inspect
import json
from pathlib import Path
from typing import Annotated, Callable, Literal, Optional

import pytest

from leetcode_local_cli.execution.nodes import (
    NodeAdapter,
    NodeConversionError,
    NodeKind,
    annotation_kind,
)
from leetcode_local_cli.execution.protocol import (
    LocalTestInputError,
    parse_parameter_assignments,
)
from leetcode_local_cli.execution.worker import LocalExecutionWorker
from leetcode_local_cli.models.execution import LocalExecutionStatus
from leetcode_local_cli.models.nodes import ListNode, TreeNode
from leetcode_local_cli.models.solution import ProblemMetadata, WorkspaceError
from leetcode_local_cli.storage.solution import (
    build_solution_content,
    parse_solution_submission,
)


@pytest.mark.parametrize(
    "annotation",
    [
        ListNode,
        ListNode | None,
        Optional[ListNode],
        Optional["ListNode"],
        "ListNode",
        "'ListNode'",
        "Optional[ListNode]",
        "typing.Optional['ListNode']",
        "ListNode | None",
        "None | ListNode",
        "Union[ListNode, None]",
    ],
)
def test_supported_node_annotations(annotation) -> None:
    assert annotation_kind(annotation) is NodeKind.LIST


@pytest.mark.parametrize(
    "annotation",
    [
        list[int],
        "list[int]",
        "int",
        inspect.Signature.empty,
        Literal["ListNode"],
        "Literal['ListNode']",
        "typing.Literal['ListNode', 'not a type expression']",
        Optional[Literal["ListNode"]],
        "Optional[Literal['ListNode']]",
        list[Literal["TreeNode"]],
        "list[typing.Literal['TreeNode']]",
        Annotated[int, "ListNode"],
        "Annotated[int, 'ListNode']",
        "typing.Annotated[int, {'note': 'TreeNode'}]",
        Callable[[Literal["ListNode"]], int],
        "Callable[[Literal['ListNode']], int]",
        "list[" * 10 + "int" + "]" * 10,
        "Optional[__import__('builtins').exec('raise RuntimeError')]",
    ],
)
def test_normal_annotations_are_not_nodes(annotation) -> None:
    assert annotation_kind(annotation) is None


@pytest.mark.parametrize(
    "annotation",
    [
        list[ListNode],
        list["ListNode"],
        "List[ListNode]",
        "list['ListNode']",
        "ListNode | int",
        "'ListNode' | int",
        "Optional[list[TreeNode]]",
        "Optional[list['TreeNode']]",
        list[Optional["ListNode"]],
        "list[Optional['ListNode']]",
        dict[str, list["TreeNode"]],
        "dict[str, list['TreeNode']]",
        "ListNode[int]",
        Annotated[ListNode, "metadata"],
        "Annotated['ListNode', 'metadata']",
        Callable[[ListNode], int],
        "Callable[['ListNode'], int]",
    ],
)
def test_nested_and_mixed_node_annotations_are_rejected(annotation) -> None:
    with pytest.raises(NodeConversionError):
        annotation_kind(annotation)


@pytest.mark.parametrize(
    "kind,cls,values,expected",
    [
        (NodeKind.LIST, ListNode, [1, 2, 3], [1, 2, 3]),
        (NodeKind.LIST, ListNode, [], []),
        (NodeKind.LIST, ListNode, None, []),
        (NodeKind.TREE, TreeNode, [1, None, 2, 3], [1, None, 2, 3]),
        (NodeKind.TREE, TreeNode, [1, 2, 3, None, None], [1, 2, 3]),
        (NodeKind.TREE, TreeNode, [], []),
        (NodeKind.TREE, TreeNode, [None], []),
    ],
)
def test_node_arrays_round_trip(kind, cls, values, expected) -> None:
    adapter = NodeAdapter(kind, cls)
    assert adapter.to_array(adapter.from_array(values)) == expected


@pytest.mark.parametrize(
    "kind,cls,values",
    [
        (NodeKind.LIST, ListNode, [None]),
        (NodeKind.LIST, ListNode, [True]),
        (NodeKind.LIST, ListNode, [1.0]),
        (NodeKind.LIST, ListNode, (1, 2)),
        (NodeKind.TREE, TreeNode, [None, 1]),
        (NodeKind.TREE, TreeNode, [1, None, None, 2]),
        (NodeKind.TREE, TreeNode, ["1"]),
    ],
)
def test_invalid_node_input_is_rejected(kind, cls, values) -> None:
    with pytest.raises(NodeConversionError):
        NodeAdapter(kind, cls).from_array(values)


def test_cycle_shared_identity_and_node_limit_are_explicit_errors(monkeypatch) -> None:
    from leetcode_local_cli.execution import nodes

    head = ListNode(1)
    head.next = head
    with pytest.raises(NodeConversionError, match="环或共享"):
        NodeAdapter(NodeKind.LIST, ListNode).to_array(head)
    child = TreeNode(2)
    with pytest.raises(NodeConversionError, match="环或共享"):
        NodeAdapter(NodeKind.TREE, TreeNode).to_array(TreeNode(1, child, child))
    monkeypatch.setattr(nodes, "MAX_NODES", 2)
    adapter = NodeAdapter(NodeKind.LIST, ListNode)
    with pytest.raises(NodeConversionError, match="超过"):
        adapter.from_array([1, 2, 3])
    with pytest.raises(NodeConversionError, match="超过"):
        adapter.to_array(ListNode(1, ListNode(2, ListNode(3))))


def test_long_list_and_skewed_tree_do_not_recurse() -> None:
    for kind, cls in ((NodeKind.LIST, ListNode), (NodeKind.TREE, TreeNode)):
        values = (
            list(range(2000))
            if kind is NodeKind.LIST
            else [0, *[item for i in range(1, 2000) for item in (None, i)]]
        )
        adapter = NodeAdapter(kind, cls)
        assert adapter.to_array(adapter.from_array(values)) == values


def test_null_is_an_ast_literal_alias_not_text_replacement() -> None:
    assert parse_parameter_assignments('root = [1, null, 2], text = "null"') == {
        "root": [1, None, 2],
        "text": "null",
    }
    for raw in (
        "root = null()",
        "root = null.attr",
        "root = [x for x in null]",
        "root = __import__('os')",
    ):
        with pytest.raises(LocalTestInputError):
            parse_parameter_assignments(raw)


def _generated(path: Path, body: str) -> None:
    path.write_text(
        build_solution_content(body, ProblemMetadata("1", "1", "Example", "example")),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "kind,name,values",
    [("ListNode", "head", [1, 2, 3]), ("TreeNode", "root", [1, None, 2, 3])],
)
@pytest.mark.parametrize("future", [False, True])
def test_generated_template_executes_nodes_and_excludes_helpers_from_submission(
    tmp_path, kind, name, values, future
) -> None:
    path = tmp_path / "solution.py"
    body = f"class Solution:\n    def echo(self, {name}: Optional[{kind}]) -> Optional[{kind}]:\n        return {name}\n"
    _generated(path, body)
    if future:
        path.write_text(
            "from __future__ import annotations\n" + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    _, submission = parse_solution_submission(path)
    assert submission == body.strip()
    assert "class ListNode" not in submission and "class TreeNode" not in submission
    with LocalExecutionWorker(path, timeout=2) as worker:
        result = worker.execute({name: values})
        empty = worker.execute({name: []})
    assert result.status is LocalExecutionStatus.SUCCEEDED, result.error
    assert json.loads(result.result_text) == values
    assert json.loads(empty.result_text) == []


def test_node_mutation_and_normal_list_meaning_are_preserved(tmp_path) -> None:
    path = tmp_path / "solution.py"
    _generated(
        path,
        "class Solution:\n    def mutate(self, head: ListNode, nums: list[int]) -> None:\n        head.val = nums[0]\n        nums.append(7)\n",
    )
    with LocalExecutionWorker(path, timeout=2) as worker:
        result = worker.execute({"head": [1, 2], "nums": [9]})
        again = worker.execute({"head": [1, 2], "nums": [9]})
    assert result.status is LocalExecutionStatus.SUCCEEDED
    assert json.loads(result.arguments_after_text or "null") == {
        "head": [9, 2],
        "nums": [9, 7],
    }
    assert result.arguments_after_text == again.arguments_after_text


@pytest.mark.parametrize(
    "body,message",
    [
        ("head.next = head\n        return head", "环或共享"),
        ("return [head]", "嵌套节点"),
        ("head.val = 'text'\n        return head", "只支持整数"),
    ],
)
def test_unsupported_node_result_is_failed_case_not_worker_crash(
    tmp_path, body, message
) -> None:
    path = tmp_path / "solution.py"
    _generated(
        path, f"class Solution:\n    def run(self, head: ListNode):\n        {body}\n"
    )
    with LocalExecutionWorker(path, timeout=2) as worker:
        for _ in range(2):
            result = worker.execute({"head": [1, 2]})
            assert result.status is LocalExecutionStatus.FAILED
            assert message in result.error


def test_missing_annotation_does_not_guess_parameter_name(tmp_path) -> None:
    path = tmp_path / "solution.py"
    _generated(
        path, "class Solution:\n    def run(self, head):\n        return head.val\n"
    )
    with LocalExecutionWorker(path, timeout=2) as worker:
        result = worker.execute({"head": [1]})
    assert result.status is LocalExecutionStatus.FAILED
    assert "补充 ListNode/TreeNode" in result.error


@pytest.mark.parametrize("future", [False, True])
@pytest.mark.parametrize("annotation", ["list[ListNode]", "list['ListNode']"])
def test_nested_node_annotation_fails_at_startup(tmp_path, future, annotation) -> None:
    path = tmp_path / "solution.py"
    _generated(
        path,
        f"class Solution:\n    def run(self, heads: {annotation}):\n        return heads\n",
    )
    if future:
        path.write_text(
            "from __future__ import annotations\n" + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    with pytest.raises(WorkspaceError, match="嵌套"):
        LocalExecutionWorker(path, timeout=2).start()


@pytest.mark.parametrize("future", [False, True])
@pytest.mark.parametrize(
    "annotation", ["Literal['ListNode']", "Annotated[str, 'TreeNode']"]
)
def test_annotation_value_strings_do_not_trigger_node_conversion(
    tmp_path, future, annotation
) -> None:
    path = tmp_path / "solution.py"
    path.write_text(
        ("from __future__ import annotations\n" if future else "")
        + "from typing import Literal, Annotated\n"
        + f"class Solution:\n    def run(self, value: {annotation}):\n        return value\n",
        encoding="utf-8",
    )
    with LocalExecutionWorker(path, timeout=2) as worker:
        result = worker.execute({"value": "ListNode"})
    assert result.status is LocalExecutionStatus.SUCCEEDED, result.error
    assert json.loads(result.result_text) == "ListNode"


@pytest.mark.parametrize("verbose", [False, True])
def test_error_line_and_opt_in_traceback_do_not_capture_locals(
    tmp_path, verbose
) -> None:
    path = tmp_path / "solution.py"
    path.write_text(
        "class Solution:\n    def run(self, value):\n        local_only = 'DO_NOT_CAPTURE_LOCALS'\n        print('before error')\n        return value / 0\n",
        encoding="utf-8",
    )
    with LocalExecutionWorker(path, timeout=2, verbose=verbose) as worker:
        result = worker.execute({"value": 1})
    assert result.error_line == 5
    assert result.stdout == "before error\n"
    assert bool(result.traceback) is verbose
    assert "DO_NOT_CAPTURE_LOCALS" not in result.traceback
    assert result.error == "ZeroDivisionError: division by zero"
