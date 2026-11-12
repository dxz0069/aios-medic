"""中间件单元测试（纯本地可跑，无外部依赖）。"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from middleware import MessageBus, Scheduler, Task, Workspace  # noqa: E402


def _fake_agent_factory(durations=None, record=None):
    durations = durations or {}

    def factory(name):
        class A:
            def __init__(self):
                self.agent_name = name

            def run(self, task_input):
                if record is not None:
                    record.append((name, time.time(), threading.get_name()))
                d = durations.get(name, 0.05)
                time.sleep(d)
                return {"agent_name": name, "result": {"echo": task_input},
                        "diagnosis_ok": True}

        return A()
    return factory


def test_topo_order_respects_deps():
    tasks = [Task("T5", "diagnostician", lambda u: "5", deps=("T2",)),
             Task("T2", "metric", lambda u: "2", deps=("T0",)),
             Task("T0", "commander", lambda u: "0")]
    order = [t.id for t in Scheduler._topo(tasks)]
    assert order.index("T0") < order.index("T2") < order.index("T5")


def test_topo_detects_cycle():
    tasks = [Task("A", "a", lambda u: "", deps=("B",)), Task("B", "b", lambda u: "", deps=("A",))]
    try:
        Scheduler._topo(tasks)
        assert False, "cycle not detected"
    except ValueError:
        pass


def test_serial_and_concurrent_same_results():
    def build():
        return [Task("T0", "commander", lambda u: "plan"),
                *[Task(f"T{i}", f"analyst{i}",
                       lambda u, i=i: str(i), deps=("T0",)) for i in range(1, 5)],
                Task("T5", "diag", lambda u: sorted(u.keys()))]

    for mode in ("serial", "concurrent"):
        out = Scheduler(MessageBus(), mode=mode, max_workers=4).run(build(), _fake_agent_factory())
        assert set(out["results"].keys()) == {"T0", "T1", "T2", "T3", "T4", "T5"}
        # fake agent 将输入包装为 {"result": {"echo": 输入}} —— T5 的上游=其声明的依赖 T1..T4
        assert out["results"]["T5"]["result"]["echo"] == ["T1", "T2", "T3", "T4"]


def test_concurrent_faster_than_serial():
    durs = {f"analyst{i}": 0.4 for i in range(1, 5)}
    def build():
        return [Task("T0", "commander", lambda u: "p", ),
                *[Task(f"T{i}", f"analyst{i}", lambda u: "", deps=("T0",)) for i in range(1, 5)]]

    s = Scheduler(MessageBus(), mode="serial").run(build(), _fake_agent_factory(durs))
    c = Scheduler(MessageBus(), mode="concurrent", max_workers=4).run(build(), _fake_agent_factory(durs))
    assert s["wall_s"] >= 4 * 0.35
    assert c["wall_s"] < s["wall_s"] / 2  # 并行4路至少省一半以上


def test_messagebus_log_and_poll(tmp_path):
    ws = Workspace(str(tmp_path), run_id="t1")
    bus = MessageBus(ws)
    bus.emit("A", "B", "PING", {"k": 1}, round_=2)
    msgs = bus.poll("B")
    assert len(msgs) == 1 and msgs[0].payload == {"k": 1} and msgs[0].round == 2
    assert bus.poll("B") == []  # 取走即清
    line = ws.path("messages.jsonl").read_text(encoding="utf-8").strip()
    assert '"from": "A"' in line and '"type": "PING"' in line


def test_workspace_roundtrip(tmp_path):
    ws = Workspace(str(tmp_path), run_id="t2")
    ws.write_json("reports/a.json", {"x": 1})
    assert ws.read_json("reports/a.json") == {"x": 1}
