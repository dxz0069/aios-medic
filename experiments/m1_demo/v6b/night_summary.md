# M1 夜间构建汇总

| 故障 | 串行均值(s) | 并发均值(s) | 提速% | 类目正确 | 组件正确 | 恢复成功 | 结论(并发末轮) |
|---|---|---|---|---|---|---|---|
| F06 | 114.83 | 94.18 | 18.0 | 1/8 | 2/8 | 2/8 | service/crash / toy-critical-service |
| F10 | 129.79 | 102.89 | 20.7 | 1/8 | 1/8 | 1/8 | resource/cpu|resource/process / python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5\7B-Instruct --port 8191 --attn eager --batch-window-ms 500 --max-batch 8 |
| F18 | 143.41 | 115.46 | 19.5 | 0/8 | 0/8 | 0/8 | service/crash / toy-critical-service |
