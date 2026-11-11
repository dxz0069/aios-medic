# Spike ① — 7B 诊断单输出可靠性测试

**用途**：M0 kill-switch 依据。验证 Qwen2.5-7B 在 LogAnalyst 风格提示词下，对单源日志/指标片段输出结构化 JSON 诊断单的可靠性。

**判定口径**：`kill-switch 失败率 = 1 - min(JSON解析成功率, 类目准确率)`；**> 30% 触发场景回退**（Medic → DevForge，见 `note/design/系统设计方案.md` §12）。

## 运行

```bash
# 真实模型（vLLM 端点；ollama 同理换 base-url 与 model）
python experiments/spike1/run_spike1.py \
    --base-url http://127.0.0.1:8091/v1 \
    --model Qwen/Qwen2.5-7B-Instruct-AWQ

# 链路自检（不调 LLM）
python experiments/spike1/run_spike1.py --selftest
```

结果输出至 `experiments/spike1/results/`（`spike1_report.md` 人读版 + `spike1_results.json` 机器版，含每条原始输出），`results/` 已加入 `.gitignore`（原始输出较大，只提交汇总报告摘要）。

## 样本说明

`samples/` 下 5 个文件共 20 条样本（每故障类别 4 条），**均为合成样本**（`synthetic: true`），手工构造以贴近 dmesg/ps/sar/df/ping/tc/journal 等真实工具的输出格式；金标签 = 类目 + 组件 + 关键证据行。类别集合与 `testbed/signatures/signatures.json` 保持一致：

| 故障 | 类别 | 样本源 |
|---|---|---|
| F01 内存泄漏 | resource/memory | dmesg OOM、ps RSS、leaky.log、sar -r |
| F02 磁盘写满 | resource/disk | df -h、应用 ENOSPC 日志、df -i、du |
| F03 CPU 饱和 | resource/cpu | loadavg、pidstat、vmstat、top |
| F04 服务崩溃 | service/crash | service.log 重启循环、curl 拒连、dmesg segfault、journal |
| F05 网络丢包 | network/loss | ping、tc qdisc、ss -ti、应用超时日志 |
