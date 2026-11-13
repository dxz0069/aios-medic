# M1 夜间构建汇总

| 故障 | 串行均值(s) | 并发均值(s) | 提速% | 类目正确 | 组件正确 | 恢复成功 | 结论(并发末轮) |
|---|---|---|---|---|---|---|---|
| F01 | 99.77 | 71.92 | 27.9 | 5/6 | 1/6 | 6/6 | resource/memory / lekcy.py |
| F03 | 185.07 | 139.76 | 24.5 | 5/6 | 5/6 | 5/6 | resource/cpu / python3 -c 'import multiprocessing as mp, os; def _burn(): while True: pass; ...' |
| F04 | 78.32 | 63.78 | 18.6 | 6/6 | 6/6 | 6/6 | service/crash / toy-critical-service |
