"""诊断 —— 解析层和格式化层共用的警告形状。

`--report json`、插件日志、`render_warnings` 都直接吃这个结构，
所以 dict 形状只在这里定义一份，避免两层各写一遍。
"""
from __future__ import annotations


def warn(ctx: dict, message: str, line: int = 0) -> None:
    """往 ctx 里追加一条警告。line 是 1-based 行号（0 = 不知道）。"""
    ctx["warnings"].append({"message": message, "line": line})
