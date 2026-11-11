"""Workspace —— 共享工件区（OS 叙事：文件系统）。

按 run_id 组织目录：采集快照 / 各智能体诊断单 / 根因结论 / 时间线 / 消息日志。
智能体间传引用（相对路径）不传大文本，控制 7B 上下文长度。
"""
import json
import time
from pathlib import Path


class Workspace:
    def __init__(self, root: str, run_id: str | None = None):
        self.root = Path(root)
        self.run_id = run_id or time.strftime("run%m%d-%H%M%S")
        self.dir = self.root / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, rel: str) -> Path:
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write_json(self, rel: str, obj) -> Path:
        p = self.path(rel)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def read_json(self, rel: str):
        return json.loads(self.path(rel).read_text(encoding="utf-8"))

    def write_text(self, rel: str, text: str) -> Path:
        p = self.path(rel)
        p.write_text(text, encoding="utf-8")
        return p
