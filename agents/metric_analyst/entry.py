"""Medic MetricAnalyst 智能体：指标水位分析（loadavg/meminfo/df 等）。"""
import json

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output

CATEGORIES = "resource/memory|resource/disk|resource/cpu|service/crash|network/loss|none"

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统中的指标分析智能体。给定来自 Linux 受控环境的"
    "资源指标片段（/proc/loadavg、/proc/meminfo、df、vmstat 等），判断水位是否异常。"
    "关注：负载 vs CPU 数、内存可用比例、磁盘使用率、runnable 队列长度。"
    "仅输出一个 JSON 对象，不要输出任何其他文字或代码块标记，字段如下：\n"
    '{"category": "' + CATEGORIES + '",\n'
    ' "component": "定位到的组件（进程名/目录/设备），无异常为空字符串",\n'
    ' "confidence": 0.0到1.0的数字,\n'
    ' "anomalies": ["异常现象描述"],\n'
    ' "evidence": ["引用原文的关键数值"],\n'
    ' "need_more": "证据不足时指出需补充采集的源(log/metric/proc/net)，否则为空字符串"}'
)

MAX_RETRY = 3


class MetricAnalystAgent:
    def __init__(self, agent_name: str = "metric_analyst"):
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
        source, snippet = "metric", task_input or ""
        try:
            data = json.loads(task_input)
            if isinstance(data, dict):
                source, snippet = data.get("source", "metric"), data.get("snippet", "")
        except (json.JSONDecodeError, TypeError):
            pass

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"指标片段（来源: {source}）:\n\n{snippet}"},
        ]
        result, last_raw = None, ""
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
            result = self._extract_json(raw)
            if result is not None:
                break
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "上一个输出不是合法 JSON。仅重新输出 JSON 对象本身。"})
        return {"agent_name": self.agent_name,
                "result": result if result is not None else last_raw,
                "rounds": self.rounds, "diagnosis_ok": result is not None}
