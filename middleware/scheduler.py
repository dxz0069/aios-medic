"""DAGScheduler —— 依赖约束下的任务调度器（OS 叙话：进程调度器）。

两种模式（性能对比实验的公正性保证——同一套智能体与输入，仅调度不同）：
- SERIAL：按拓扑序逐个执行（串行基线）
- CONCURRENT：依赖就绪即派发（线程池并发），完成事件驱动下游

Task.input_builder(results) 在任务启动时以"上游全部结果"构造该任务的输入，
天然实现依赖传递。所有调度事件经 MessageBus 落盘。
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .messagebus import MessageBus


class Task:
    def __init__(self, tid: str, agent_name: str, input_builder, deps: tuple = (), meta: dict | None = None):
        self.id, self.agent_name = tid, agent_name
        self.input_builder, self.deps, self.meta = input_builder, tuple(deps), meta or {}


class Scheduler:
    def __init__(self, bus: MessageBus, mode: str = "concurrent", max_workers: int = 4):
        assert mode in ("serial", "concurrent")
        self.bus, self.mode, self.max_workers = bus, mode, max_workers
        self.timeline: list[dict] = []

    def _exec(self, task: Task, agent_factory, results: dict, lock: threading.Lock):
        with lock:
            upstream = {k: results[k] for k in task.deps if k in results}
        task_input = task.input_builder(upstream)
        self.bus.emit("SCHEDULER", task.agent_name, "TASK_DISPATCH",
                      {"task_id": task.id, "deps": list(task.deps), "mode": self.mode})
        agent = agent_factory(task.agent_name)
        start = time.time()
        try:
            res = agent.run(task_input)
            ok = bool(res.get("diagnosis_ok", res.get("plan_ok", True)))
        except Exception as e:  # noqa: BLE001 - 调度器必须兜住智能体异常
            res, ok = {"agent_name": task.agent_name, "error": str(e)}, False
        dur = round(time.time() - start, 2)
        with lock:
            results[task.id] = res
        self.timeline.append({"task_id": task.id, "agent": task.agent_name,
                              "start": round(start, 2), "dur_s": dur, "ok": ok,
                              "deps": list(task.deps)})
        self.bus.emit(task.agent_name, "SCHEDULER", "TASK_DONE",
                      {"task_id": task.id, "dur_s": dur, "ok": ok})
        return res

    def run(self, tasks: list[Task], agent_factory):
        results: dict = {}
        lock = threading.Lock()
        t0 = time.time()
        if self.mode == "serial":
            for task in self._topo(tasks):
                self._exec(task, agent_factory, results, lock)
        else:
            indeg = {t.id: len(t.deps) for t in tasks}
            by_id = {t.id: t for t in tasks}
            children: dict[str, list[str]] = {t.id: [] for t in tasks}
            for t in tasks:
                for d in t.deps:
                    children.setdefault(d, []).append(t.id)
            ready = [t.id for t in tasks if indeg[t.id] == 0]
            cv = threading.Condition()
            state = {"done": 0, "total": len(tasks)}

            def run_one(tid):
                task = by_id[tid]
                self._exec(task, agent_factory, results, lock)
                with cv:
                    for c in children.get(tid, []):
                        indeg[c] -= 1
                        if indeg[c] == 0:
                            pool.submit(run_one, c)
                    state["done"] += 1
                    cv.notify_all()

            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = [pool.submit(run_one, r) for r in ready]
                with cv:
                    while state["done"] < state["total"]:
                        cv.wait(timeout=30)
        wall = round(time.time() - t0, 2)
        return {"results": results, "timeline": sorted(self.timeline, key=lambda x: x["start"]),
                "wall_s": wall, "mode": self.mode}

    @staticmethod
    def _topo(tasks: list[Task]) -> list[Task]:
        by_id = {t.id: t for t in tasks}
        indeg = {t.id: len(t.deps) for t in tasks}
        children: dict[str, list[str]] = {t.id: [] for t in tasks}
        for t in tasks:
            for d in t.deps:
                children.setdefault(d, []).append(t.id)
        queue = sorted([t.id for t in tasks if indeg[t.id] == 0])
        out: list[Task] = []
        while queue:
            tid = queue.pop(0)
            out.append(by_id[tid])
            for c in sorted(children.get(tid, [])):
                indeg[c] -= 1
                if indeg[c] == 0:
                    queue.append(c)
        if len(out) != len(tasks):
            raise ValueError("DAG 存在环或悬空依赖")
        return out
