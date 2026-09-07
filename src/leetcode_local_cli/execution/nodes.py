"""Annotation-directed node conversion; never evaluate annotation expressions."""

import ast
import inspect
import types
import typing
from collections import deque
from dataclasses import dataclass
from enum import Enum

MAX_NODES = 100_000


class NodeKind(str, Enum):
    LIST = "ListNode"
    TREE = "TreeNode"


class NodeConversionError(ValueError):
    pass


def _annotation_node(tree: ast.expr) -> NodeKind | None:
    if isinstance(tree, ast.Constant) and isinstance(tree.value, str):
        return _annotation_node(ast.parse(tree.value, mode="eval").body)
    if isinstance(tree, ast.Name) and tree.id in {kind.value for kind in NodeKind}:
        return NodeKind(tree.id)
    if isinstance(tree, ast.BinOp) and isinstance(tree.op, ast.BitOr):
        for node, empty in ((tree.left, tree.right), (tree.right, tree.left)):
            if isinstance(empty, ast.Constant) and empty.value is None:
                return _annotation_node(node)
    children: list[ast.expr] = []
    if isinstance(tree, ast.Subscript):
        name = ast.unparse(tree.value)
        # Literal arguments and Annotated metadata are values, not type references.
        if name in {"Literal", "typing.Literal"}:
            return None
        if name in {"Optional", "typing.Optional"}:
            return _annotation_node(tree.slice)
        if name in {"Union", "typing.Union"} and isinstance(tree.slice, ast.Tuple):
            elements = tree.slice.elts
            if len(elements) == 2:
                for node, empty in (elements, elements[::-1]):
                    if isinstance(empty, ast.Constant) and empty.value is None:
                        return _annotation_node(node)
        children = (
            tree.slice.elts if isinstance(tree.slice, ast.Tuple) else [tree.slice]
        )
        if name in {"Annotated", "typing.Annotated"}:
            children = children[:1]
        children = [tree.value, *children]
    elif isinstance(tree, ast.BinOp) and isinstance(tree.op, ast.BitOr):
        children = [tree.left, tree.right]
    elif isinstance(tree, (ast.Tuple, ast.List)):
        children = tree.elts
    if any(_annotation_node(child) is not None for child in children):
        raise NodeConversionError(
            "不支持嵌套或混合节点注解，请使用 ListNode 或 TreeNode 可空注解"
        )
    return None


def annotation_kind(annotation: object) -> NodeKind | None:
    try:
        return _runtime_annotation_node(annotation)
    except (SyntaxError, RecursionError) as exc:
        raise NodeConversionError(
            "无法识别节点注解，请补充 ListNode 或 TreeNode 注解"
        ) from exc


def _runtime_annotation_node(annotation: object) -> NodeKind | None:
    if isinstance(annotation, typing.ForwardRef):
        return _runtime_annotation_node(annotation.__forward_arg__)
    if isinstance(annotation, str):
        return _annotation_node(ast.parse(annotation, mode="eval").body)
    if isinstance(annotation, type) and annotation.__name__ in {
        kind.value for kind in NodeKind
    }:
        return NodeKind(annotation.__name__)
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return None
    args = typing.get_args(annotation)
    if origin in (typing.Union, types.UnionType) and len(args) == 2:
        nonempty = tuple(arg for arg in args if arg is not type(None))
        if len(nonempty) == 1:
            return _runtime_annotation_node(nonempty[0])
    if origin is typing.Annotated:
        args = args[:1]
    elif isinstance(annotation, list):
        # Callable stores its parameter types as a list in runtime annotations.
        args = tuple(annotation)
    if any(_runtime_annotation_node(arg) is not None for arg in args):
        raise NodeConversionError(
            "不支持嵌套或混合节点注解，请使用 ListNode 或 TreeNode 可空注解"
        )
    return None


@dataclass(frozen=True)
class NodeAdapter:
    kind: NodeKind
    node_class: type

    def from_array(self, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, list):
            raise NodeConversionError(f"{self.kind.value} 输入必须是数组或 null/None")
        if len(value) > MAX_NODES:
            raise NodeConversionError(f"节点输入超过 {MAX_NODES} 项限制")
        if any(
            type(item) is not int and not (self.kind is NodeKind.TREE and item is None)
            for item in value
        ):
            raise NodeConversionError(
                "节点值只支持整数；仅二叉树数组允许 null/None 空位"
            )
        if not value:
            return None
        if self.kind is NodeKind.LIST:
            head = None
            for item in reversed(value):
                node = self.node_class(item)
                node.next = head
                head = node
            return head
        if value[0] is None:
            if any(item is not None for item in value[1:]):
                raise NodeConversionError("二叉树存在无法连接到根节点的值")
            return None
        root = self.node_class(value[0])
        pending = deque([root])
        index = 1
        while pending and index < len(value):
            parent = pending.popleft()
            for name in ("left", "right"):
                if index == len(value):
                    break
                item = value[index]
                index += 1
                if item is not None:
                    child = self.node_class(item)
                    setattr(parent, name, child)
                    pending.append(child)
        if any(item is not None for item in value[index:]):
            raise NodeConversionError("二叉树存在无法连接到根节点的值")
        return root

    def to_array(self, root: object, seen: set[int] | None = None) -> list[int | None]:
        visited = set() if seen is None else seen
        pending = deque([root])
        result: list[int | None] = []
        count = 0
        while pending:
            node = pending.popleft()
            if node is None:
                if self.kind is NodeKind.TREE:
                    result.append(None)
                continue
            if not isinstance(node, self.node_class):
                raise NodeConversionError(
                    f"预期 {self.kind.value} 节点，实际类型不匹配"
                )
            if id(node) in visited:
                raise NodeConversionError("不支持环或共享节点身份")
            visited.add(id(node))
            count += 1
            if count > MAX_NODES:
                raise NodeConversionError(f"节点输出超过 {MAX_NODES} 项限制")
            val = getattr(node, "val", None)
            if type(val) is not int:
                raise NodeConversionError("节点值只支持整数")
            result.append(val)
            names = ("next",) if self.kind is NodeKind.LIST else ("left", "right")
            for name in names:
                if not hasattr(node, name):
                    raise NodeConversionError(f"{self.kind.value} 缺少 {name} 属性")
                pending.append(getattr(node, name))
        while result and result[-1] is None:
            result.pop()
        return result


class NodeCodec:
    def __init__(
        self, namespace: dict[str, object], signature: inspect.Signature
    ) -> None:
        self.adapters = tuple(
            NodeAdapter(kind, cls)
            for kind in NodeKind
            if isinstance(cls := namespace.get(kind.value), type)
        )
        self.parameters = {
            name: self.for_annotation(parameter.annotation)
            for name, parameter in signature.parameters.items()
        }
        self.return_adapter = self.for_annotation(signature.return_annotation)

    def for_annotation(self, annotation: object) -> NodeAdapter | None:
        kind = annotation_kind(annotation)
        if kind is None:
            return None
        for adapter in self.adapters:
            if adapter.kind is kind:
                return adapter
        raise NodeConversionError(
            f"缺少 {kind.value} 定义，请重新生成模板或补充本地定义"
        )

    def arguments(self, arguments: dict[str, object]) -> dict[str, object]:
        converted = {}
        for name, value in arguments.items():
            adapter = self.parameters.get(name)
            try:
                converted[name] = adapter.from_array(value) if adapter else value
            except NodeConversionError as exc:
                raise NodeConversionError(f"参数 {name}：{exc}") from exc
        return converted

    def result(self, value: object) -> object:
        if self.return_adapter:
            return self.return_adapter.to_array(value)
        return self._plain_value(value, allow_node=True, seen=set())

    def arguments_after(self, arguments: dict[str, object]) -> dict[str, object]:
        seen: set[int] = set()
        result = {}
        for name, value in arguments.items():
            adapter = self.parameters.get(name)
            result[name] = (
                adapter.to_array(value, seen)
                if adapter
                else self._plain_value(value, allow_node=True, seen=seen)
            )
        return result

    def _plain_value(
        self, value: object, *, allow_node: bool, seen: set[int]
    ) -> object:
        for adapter in self.adapters:
            if isinstance(value, adapter.node_class):
                if not allow_node:
                    raise NodeConversionError("暂不支持嵌套节点集合")
                return adapter.to_array(value, seen)
        if isinstance(value, (list, tuple, dict)):
            if id(value) in seen:
                raise NodeConversionError("输出包含循环容器")
            seen.add(id(value))
            try:
                if isinstance(value, dict):
                    return {
                        self._plain_value(
                            key, allow_node=False, seen=seen
                        ): self._plain_value(item, allow_node=False, seen=seen)
                        for key, item in value.items()
                    }
                items = [
                    self._plain_value(item, allow_node=False, seen=seen)
                    for item in value
                ]
                return tuple(items) if isinstance(value, tuple) else items
            finally:
                seen.remove(id(value))
        return value
