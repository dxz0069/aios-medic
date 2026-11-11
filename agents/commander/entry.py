"""Medic Commander 智能体：诊断计划生成（任务分解 → DAG）。

输入 task_input：告警快照 JSON 字符串（collect.py 的 alert 部分）。
输出：诊断计划 {"plan_id", "analysis_tasks":[{id,agent,source,reason}...], "aggregate_agent"}。
LLM 解析失败时回退确定性默认计划（4 路并行分析，保证可用性下限）。
"""
import json
import time

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output

DEFAULT_PLAN = {
    "plan_id": f"plan-{time.strftime('%m%d%H%M%S')}",
    "analysis_tasks": [
        {"id": "A1", "agent": "log_analyst", "source": "log", "reason": "内核/服务日志异常事件"},
        {"id": "A2", "agent": "metric_analyst", "source": "metric", "reason": "资源水位异常"},
        {"id": "A3", "agent": "proc_analyst", "source": "proc", "reason": "异常进程定位"},
        {"id": "A4", "agent": "net_analyst", "source": "net", "reason": "网络连通性/规则"},
    ],
    "aggregate_agent": "diagnostician",
}

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统的指挥官（Commander）。给定异常告警快照（各健康探针结果），"
    "生成多智能体并行诊断计划。四个分析智能体可用：log_analyst(日志)/metric_analyst(指标)/"
    "proc_analyst(进程)/net_analyst(网络)，诊断单由 diagnostician 聚合。"
    "仅输出一个 JSON 对象，不要输出任何其他文字，格式：\n"
    '{"plan_id": "plan-xxx", "analysis_tasks": [{"id": "A1", "agent": "log_analyst",'
    ' "source": "log", "reason": "一句话"}], "aggregate_agent": "diagnostician"}\n'
    "analysis_tasks 必须包含全部四个智能体（它们将并行执行）。"
)

MAX_RETRY = 2


class CommanderAgent:
    def __init__(self, agent_name: str = "commander"):
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

    def _validate(self, plan) -> bool:
        tasks = plan.get("analysis_tasks")
        return (isinstance(tasks, list) and len(tasks) >= 4
                and all(t.get("agent") in ("log_analyst", "metric_analyst",
                                           "proc_analyst", "net_analyst") for t in tasks))

    def run(self, task_input: str):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"告警快照:\n{task_input}"},
        ]
        plan, fallback_used, last_raw = None, False, ""
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
            last_raw = raw
            plan = self._extract_json(raw)
            if plan is not None and self._validate(plan):
                break
            plan = None
        if plan is None:  # 确定性兜底：默认四路并行计划
            plan, fallback_used = DEFAULT_PLAN, True
        return {"agent_name": self.agent_name, "result": plan, "rounds": self.rounds,
                "fallback_used": fallback_used, "plan_ok": True,
                "raw": None if not fallback_used else last_raw[:200]}
