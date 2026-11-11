"""Medic Verifier 智能体：修复验证（修复-验证回环的关键一环）。

输入 task_input：{"alert_before": {...}, "alert_after": {...}}
输出：{"recovered": bool, "evidence": [...], "comment": "..."}
LLM 不可用时回退确定性阈值判定（全部告警位为 False 即恢复）。
"""
import json

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output

FLAGS = ("cpu", "memory", "disk", "network", "service")

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统的验证智能体（Verifier）。给定修复前/修复后两组健康告警"
    "（各含 cpu/memory/disk/network/service 布尔告警位与 values 数值），判断系统是否已恢复。"
    "恢复 = 修复后所有告警位均为 false 且数值回到正常水位。"
    '仅输出 JSON：{"recovered": true或false, "evidence": ["依据"], "comment": "一句话"}'
)

MAX_RETRY = 2


class VerifierAgent:
    def __init__(self, agent_name: str = "verifier"):
        self.agent_name = agent_name
        self.rounds = 0

    @staticmethod
    def _extract_json(text: str):
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1] if "\n" in text else text
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start:end + 1])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        return None

    def run(self, task_input: str):
        try:
            data = json.loads(task_input)
            before, after = data.get("alert_before", {}), data.get("alert_after", {})
        except (json.JSONDecodeError, TypeError):
            before, after = {}, {}

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"alert_before": before, "alert_after": after}, ensure_ascii=False)},
        ]
        result, fallback_used = None, False
        for _attempt in range(MAX_RETRY):
            self.rounds += 1
            try:
                resp = llm_chat_with_json_output(
                    agent_name=self.agent_name, messages=messages,
                    message_return_type="json", base_url=sdk_config.get_kernel_url())
                raw = resp["response"]["response_message"]
            except TypeError:
                resp = llm_chat(agent_name=self.agent_name, messages=messages,
                                base_url=sdk_config.get_kernel_url())
                raw = resp["response"]["response_message"]
            result = self._extract_json(raw)
            if result is not None and isinstance(result.get("recovered"), bool):
                break
            result = None
        det_recovered = not any(bool(after.get(f)) for f in FLAGS)
        if result is None:  # 确定性回退
            result = {"recovered": det_recovered,
                      "evidence": [f"{f}={bool(after.get(f))}" for f in FLAGS],
                      "comment": "确定性阈值判定兜底"}
            fallback_used = True
        else:  # LLM 结论与确定性判定冲突时以确定性判定为准（正确性下限）
            result["recovered"] = result["recovered"] and det_recovered
        return {"agent_name": self.agent_name, "result": result, "rounds": self.rounds,
                "fallback_used": fallback_used, "deterministic_recovered": det_recovered,
                "verify_ok": True}
