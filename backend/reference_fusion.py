"""Bounded writer retry when fused references omit or invent source markers."""

import re
from .agents import complete
from .configuration import prompt, settings


def synthesize(selections, instruction, context, provider, completion=None):
    completion = completion or complete
    selected = {s["source_id"] for s in selections}
    payload = dict(selections=selections, instruction=instruction, context=context)
    for attempt in range(settings("generation").get("fusion_retries", 1) + 1):
        answer = completion(prompt("fusion") + "\n" + prompt("language-style"), payload, provider)
        text = answer.get("text") if isinstance(answer, dict) else None
        citations = {"S" + n for n in re.findall(r"\[S(\d+)\]", text if isinstance(text, str) else "")}
        if isinstance(text, str) and text.strip() and citations and citations <= selected:
            return text.strip()
        payload["correction"] = dict(
            previous_answer=answer,
            required_markers=["[" + marker + "]" for marker in sorted(selected)],
            reason="输出缺少合法来源编号。保留融合内容，仅用实际选中的 [S编号] 标注事实句，禁止省略引用或使用其他编号。仍只返回 JSON text。",
        )
    raise ValueError("融合段落缺少有效来源编号，原稿未修改")
