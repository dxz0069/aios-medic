"""Medic Repairer 智能体：白名单修复决策（LLM 决策 + 确定性校验）。

输入 task_input：{"root_cause": {...}, "alert": {...}, "last_verify": {...}|null, "round": k}
输出：{"action","target","reason"}，action 必须在白名单内；LLM 不可用/越权时按类目回退。
动作的实际执行由 testbed/repair/actions.py 确定性执行器完成（智能体只做决策）。
"""
import json

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output

WHITELIST = ("kill_by_pattern", "tc_clear", "clear_scratch", "restart_service", "none")
APPROVED_PATTERNS = {"leaky", "import multiprocessing as mp",
                     "signal.SIGKILL", "service/service.py"}
CATEGORY_FALLBACK = {
    "resource/memory": {"action": "kill_by_pattern", "target": "leaky", "reason": "类目回退：终止泄漏进程"},
    "resource/cpu": {"action": "kill_by_pattern", "target": "import multiprocessing as mp",
                     "reason": "类目回退：终止忙循环进程组"},
    "service/crash": {"action": "kill_by_pattern", "target": "signal.SIGKILL",
                      "reason": "类目回退：终止崩溃循环制造者，服务由 supervisor 自愈"},
    "network/loss": {"action": "tc_clear", "target": "eth0", "reason": "类目回退：清除 tc netem 规则"},
    "resource/disk": {"action": "clear_scratch", "target": "/var/scratch",
                      "reason": "类目回退：清理填充文件"},
    "none": {"action": "none", "target": "", "reason": "无故障无需修复"},
}

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统的修复智能体（Repairer）。给定根因结论（类目/组件/修复提示）"
    "与当前告警，从白名单中选择一个修复动作并给出理由。白名单：\n"
    "kill_by_pattern(按命令行特征终止进程) / tc_clear(删除eth0的tc规则) / "
    "clear_scratch(清空/var/scratch填充文件) / restart_service(重启关键服务) / none(不动作)\n"
    "若选 kill_by_pattern，target 必须是以下特征串之一："
    "'leaky' / 'import multiprocessing as mp' / 'signal.SIGKILL' / 'service/service.py'；"
    "其他动作的 target 填 eth0 或 /var/scratch 或留空。\n"
    "仅输出一个 JSON 对象：{\"action\": \"...\", \"target\": \"...\", \"reason\": \"一句话\"}"
)

MAX_RETRY = 2


class RepairerAgent:
    def __init__(self, agent_name: str = "repairer"):
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
            root_cause = data.get("root_cause", {})
        except (json.JSONDecodeError, TypeError):
            data, root_cause = {}, {}
        category = root_cause.get("category", "none")
        component = root_cause.get("component", "")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"root_cause": root_cause, "alert": data.get("alert"),
                 "last_verify": data.get("last_verify"), "round": data.get("round", 1)},
                ensure_ascii=False)},
        ]
        decision, fallback_used = None, False
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
            decision = self._extract_json(raw)
            if decision and decision.get("action") in WHITELIST:
                target = decision.get("target") or ""
                if decision["action"] == "kill_by_pattern" and target not in APPROVED_PATTERNS:
                    decision = None  # 进程特征未获批准，视为无效决策
                    continue
                decision.setdefault("target", component or "")
                decision.setdefault("reason", "")
                break
            decision = None
        if decision is None:  # LLM 不可用或越权 → 类目回退
            decision = CATEGORY_FALLBACK.get(category, CATEGORY_FALLBACK["none"]).copy()
            fallback_used = True
        return {"agent_name": self.agent_name, "result": decision, "rounds": self.rounds,
                "fallback_used": fallback_used, "repair_ok": True}
