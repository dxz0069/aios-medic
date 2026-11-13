"""Medic Diagnostician 智能体：多源证据聚合 → 根因结论。

输入 task_input：JSON 字符串 {"alert": {...}, "diagnoses": {"A1": {...诊断单...}, ...}}。
输出：根因结论 {"category","component","confidence","reasoning","evidence","repair_hint"}。
LLM 失败或低置信时回退确定性加权投票（按各源置信度加权取多数类目）。
"""
import json

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统的根因综合智能体（Diagnostician）。给定异常告警与四路分析"
    "智能体的诊断单（日志/指标/进程/网络），请聚合证据，给出统一根因结论。"
    "多个源指向同一类目时置信度应提高；相互矛盾时降低置信度并在 evidence 中说明分歧。"
    "**component 必须原样摘自证据原文中的进程名/命令行片段/挂载点/网卡名/服务名"
    "（如 ps 的 COMMAND、df 的路径、tc 的设备名），禁止自行改写、缩写或凭记忆拼写。**"
    "判别提示：服务反复退出且 ss 显示其端口被其他进程持有 → network/port（端口冲突），"
    "而非 service/crash；大量 defunct 僵尸进程 → resource/process。"
    "仅输出一个 JSON 对象，不要输出任何其他文字，格式：\n"
    '{"category": "resource/memory|resource/disk|resource/cpu|resource/process|service/crash|network/loss|network/port|log/storm|none",\n'
    ' "component": "组件名", "confidence": 0.0到1.0,\n'
    ' "reasoning": "两三句推理过程", "evidence": ["各源关键证据"],\n'
    ' "repair_hint": "一句话修复建议（kill/重启/清理/回滚/删tc规则）"}'
)

MAX_RETRY = 2


def _weighted_vote(diagnoses: dict) -> dict:
    """确定性兜底：按置信度加权的类目投票 + 取最高置信源的组件。"""
    scores: dict[str, float] = {}
    best_comp, best_conf = "", 0.0
    for diag in diagnoses.values():
        res = diag.get("result") if isinstance(diag, dict) else None
        if not isinstance(res, dict):
            continue
        cat = res.get("category", "none")
        conf = float(res.get("confidence", 0.5) or 0.5)
        scores[cat] = scores.get(cat, 0.0) + conf
        if cat != "none" and conf > best_conf:
            best_conf, best_comp = conf, res.get("component", "")
    category = max(scores, key=scores.get) if scores else "none"
    return {"category": category, "component": best_comp,
            "confidence": round(min(1.0, scores.get(category, 0.0) / 2.0), 2),
            "reasoning": "确定性加权投票兜底", "evidence": [], "repair_hint": ""}


class DiagnosticianAgent:
    def __init__(self, agent_name: str = "diagnostician"):
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
            alert, diagnoses = data.get("alert", {}), data.get("diagnoses", {})
        except (json.JSONDecodeError, TypeError):
            alert, diagnoses = {}, {}
        condensed = {k: (v.get("result") if isinstance(v, dict) else v)
                     for k, v in diagnoses.items()}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"alert": alert, "diagnoses": condensed}, ensure_ascii=False)},
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
            if result is not None and result.get("category"):
                break
            result = None
        if result is None:
            result, fallback_used = _weighted_vote(diagnoses), True
        return {"agent_name": self.agent_name, "result": result, "rounds": self.rounds,
                "fallback_used": fallback_used, "diagnosis_ok": True}
