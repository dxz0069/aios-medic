"""Medic LogAnalyst 智能体（Cerebrum SDK 规范）。

输入 task_input：原始文本片段，或 JSON 字符串 {"source": "...", "snippet": "..."}。
输出：诊断单 dict（category/component/confidence/anomalies/evidence/need_more）。
LLM 调用经 AIOS Kernel 调度（base_url 取自 SDK 配置 kernel.base_url）。
"""
import json

from cerebrum.config.config_manager import config as sdk_config
from cerebrum.llm.apis import llm_chat, llm_chat_with_json_output

CATEGORIES = "resource/memory|resource/disk|resource/cpu|service/crash|network/loss|none"

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统中的日志分析智能体。给定一段来自 Linux 受控环境的"
    "工具输出片段（dmesg/ps/sar/df/ping/tc/服务日志等），判断是否存在异常。"
    "仅输出一个 JSON 对象，不要输出任何其他文字或代码块标记，字段如下：\n"
    '{"category": "' + CATEGORIES + '",\n'
    ' "component": "定位到的组件（进程名/目录/设备/服务名），无异常为空字符串",\n'
    ' "confidence": 0.0到1.0的数字,\n'
    ' "anomalies": ["异常现象描述"],\n'
    ' "evidence": ["引用原文的关键行"],\n'
    ' "need_more": "证据不足时指出需补充采集的源(log/metric/proc/net)，否则为空字符串"}'
)

MAX_RETRY = 3


class LogAnalystAgent:
    def __init__(self, agent_name: str = "log_analyst"):
        self.agent_name = agent_name
        self.rounds = 0

    @staticmethod
    def _extract_json(text: str):
        text = (text or "").strip()
        if text.startswith("```"):  # 剥离代码围栏
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
        source, snippet = "unknown", task_input or ""
        try:  # 允许结构化输入 {"source","snippet"}，也容忍纯文本
            data = json.loads(task_input)
            if isinstance(data, dict):
                source, snippet = data.get("source", "unknown"), data.get("snippet", "")
        except (json.JSONDecodeError, TypeError):
            pass

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"工具输出片段（来源: {source}）:\n\n{snippet}"},
        ]
        result, last_raw = None, ""
        for _attempt in range(MAX_RETRY):
            self.rounds += 1
            try:
                resp = llm_chat_with_json_output(
                    agent_name=self.agent_name, messages=messages,
                    message_return_type="json",
                    base_url=sdk_config.get_kernel_url(),
                )
                raw = resp["response"]["response_message"]
            except TypeError:  # SDK 版本签名差异兜底
                resp = llm_chat(agent_name=self.agent_name, messages=messages,
                                base_url=sdk_config.get_kernel_url())
                raw = resp["response"]["response_message"]
            last_raw = raw
            result = self._extract_json(raw)
            if result is not None:
                break
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",
                             "content": "上一个输出不是合法 JSON。仅重新输出 JSON 对象本身。"})

        return {
            "agent_name": self.agent_name,
            "result": result if result is not None else last_raw,
            "rounds": self.rounds,
            "diagnosis_ok": result is not None,
        }
