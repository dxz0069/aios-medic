"""MessageBus —— 智能体间消息总线（OS 叙事：IPC）。

M1 阶段：协议审计通道。所有协作事件（调度分发/完成/回环消息）经总线落盘
JSONL（messages.jsonl），供演示回放与"双向交互"证据留存。
M2 阶段：质询回采（Diagnostician↔Analyst）、修复-验证回环将走同一总线。

线程安全。
"""
import json
import threading
import time
import uuid
from pathlib import Path


class Message:
    __slots__ = ("msg_id", "ts", "frm", "to", "type", "round", "payload")

    def __init__(self, frm: str, to: str, type_: str, payload: dict, round_: int = 0):
        self.msg_id = uuid.uuid4().hex[:12]
        self.ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time()*1000)%1000:03d}Z"
        self.frm, self.to, self.type = frm, to, type_
        self.round, self.payload = round_, payload

    def to_dict(self) -> dict:
        return {"msg_id": self.msg_id, "ts": self.ts, "from": self.frm, "to": self.to,
                "type": self.type, "round": self.round, "payload": self.payload}


class MessageBus:
    def __init__(self, workspace=None):
        self._lock = threading.Lock()
        self._inboxes: dict[str, list] = {}
        self._log_path = None
        self._count = 0
        if workspace is not None:
            self._log_path = Path(workspace.path("messages.jsonl"))

    def emit(self, frm: str, to: str, type_: str, payload: dict, round_: int = 0) -> Message:
        msg = Message(frm, to, type_, payload, round_)
        with self._lock:
            self._count += 1
            self._inboxes.setdefault(to, []).append(msg)
            if self._log_path is not None:
                with self._log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        return msg

    def poll(self, who: str):
        """取走 who 收件箱中的全部消息（M2 回环智能体使用）。"""
        with self._lock:
            msgs = self._inboxes.get(who, [])
            self._inboxes[who] = []
            return msgs

    @property
    def count(self) -> int:
        return self._count
