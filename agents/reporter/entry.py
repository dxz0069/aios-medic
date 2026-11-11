"""Medic Reporter 智能体：人话诊断报告（自由文本 Markdown）。

输入 task_input：本次运行的浓缩摘要 JSON（根因/动作/验证/耗时）。
输出：Markdown 报告文本；LLM 失败时用确定性模板兜底。
"""
import json

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统的报告智能体。根据给定的运行摘要（根因结论、修复动作、"
    "验证结果、各智能体耗时），写一份简洁的中文 Markdown 诊断报告，包含："
    "## 结论 / ## 证据链 / ## 修复过程 / ## 后续建议 四节。直接输出 Markdown 正文。"
)


def _template(data: dict) -> str:
    rc = data.get("root_cause", {})
    return (
        "# Medic 诊断报告（模板兜底）\n\n"
        f"## 结论\n- 类目: {rc.get('category')}  组件: {rc.get('component')}"
        f"  置信度: {rc.get('confidence')}\n\n"
        f"## 证据链\n{json.dumps(rc.get('evidence', []), ensure_ascii=False)}\n\n"
        "## 修复过程\n"
        + "\n".join(f"- 第{k}轮: {a.get('action')} target={a.get('target')}"
                    for k, a in enumerate(data.get("repair_actions", []), 1))
        + f"\n\n## 后续建议\n- 验证结果: recovered={data.get('recovered')}\n")


class ReporterAgent:
    def __init__(self, agent_name: str = "reporter"):
        self.agent_name = agent_name
        self.rounds = 0

    def run(self, task_input: str):
        try:
            data = json.loads(task_input)
        except (json.JSONDecodeError, TypeError):
            data = {}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
        ]
        self.rounds += 1
        try:
            resp = llm_chat(agent_name=self.agent_name, messages=messages,
                            base_url=sdk_config.get_kernel_url())
            md = resp["response"]["response_message"]
            fallback_used = False
        except Exception:  # noqa: BLE001 - 报告必须有产出
            md, fallback_used = _template(data), True
        if not isinstance(md, str) or len(md.strip()) < 30:
            md, fallback_used = _template(data), True
        return {"agent_name": self.agent_name, "result": md, "rounds": self.rounds,
                "fallback_used": fallback_used, "report_ok": True}
