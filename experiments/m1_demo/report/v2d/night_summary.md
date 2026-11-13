# M1 夜间构建汇总

| 故障 | 串行均值(s) | 并发均值(s) | 提速% | 类目正确 | 组件正确 | 恢复成功 | 结论(并发末轮) |
|---|---|---|---|---|---|---|---|
| F01 | 100.69 | 62.18 | 38.2 | 4/6 | 0/6 | 6/6 | resource/disk / /dev/sda1 |
| F03 | 121.54 | 138.43 | -13.9 | 6/6 | 6/6 | 6/6 | resource/cpu / python3 -c _burn |
| F04 | 74.57 | 50.73 | 32.0 | 1/6 | 2/6 | 6/6 | resource/cpu / python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.57B-Instruct --port 8191 --attn eager --batch-window-ms 50 --max-batch 8 |
