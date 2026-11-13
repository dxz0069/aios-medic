# M1 夜间构建汇总

| 故障 | 串行均值(s) | 并发均值(s) | 提速% | 类目正确 | 组件正确 | 恢复成功 | 结论(并发末轮) |
|---|---|---|---|---|---|---|---|
| F01 | 99.16 | 68.15 | 31.3 | 5/6 | 0/6 | 5/6 | resource/memory / leee.py |
| F03 | 123.57 | 152.64 | -23.5 | 6/6 | 5/6 | 6/6 | resource/cpu / python3 -c  import multiprocessing as mp, os def _burn(): while True pass def _ncpu(): try return max(1, len(os.sched_getaffinity(0))) except (AttributeError, OSError): return os.cpu_count() or 1 if __name__ == "__main__": n = min(32, max(2, _ncpu() * 2)) prooces = [mp.Process(target=_burn) for _ in range(n)] for p in prooces: p.start() for p in prooces: p.join() |
| F04 | 93.57 | 58.53 | 37.4 | 5/6 | 6/6 | 5/6 | service/crash / toy-critical-service |
