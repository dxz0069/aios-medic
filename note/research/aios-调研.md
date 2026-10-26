# AIOS 定点调研笔记

> 调研日期：2026-10-26。调研目的：为"智能体操作系统中的多智能体协作技术"赛题做技术选型，不做铺开式调研，只回答三个问题：AIOS 当前形态如何、"AIOS-Agent SDK"指什么、如何接 7B/8B 端侧模型。
> 以下所有结论均来自公开仓库与文档原文，未做推测；不确定的点在文末"待克隆确认"一节单独列出。

## 1. AIOS 的当前形态：Kernel + SDK 双仓库

AIOS（AI Agent Operating System，Rutgers AGI Research / Yongfeng Zhang 团队）在 2024-11-30 的 v0.2 版本起拆分为两个仓库（来源：AIOS 仓库 README News 一节，https://github.com/agiresearch/AIOS）：

- **AIOS Kernel**（仓库 `agiresearch/AIOS`）：OS 内核抽象层，管理智能体所需的各类资源——LLM、内存（Memory Manager）、存储（Storage Manager）、工具（Tool Manager）、上下文管理（Context Manager）等；智能体的请求经"系统调用链"被调度并分发到各模块执行。
- **AIOS SDK**（仓库 `agiresearch/Cerebrum`，即 Cerebrum，论文全称 *Cerebrum (AIOS SDK): A Platform for Agent Development, Deployment, Distribution, and Discovery*，NAACL 2025）：面向智能体开发者/用户的 SDK，通过调用 AIOS Kernel 提供的能力来构建和运行智能体应用。PyPI 包名 `cerebrum`（2024-11-26 上架）。

赛题原文说"使用 AIOS-Agent SDK 设计多智能体协作系统"，对应的技术路线即：**AIOS Kernel（`agiresearch/AIOS`）+ Cerebrum SDK（`agiresearch/Cerebrum`）**。

注意：`https://github.com/agiresearch/aios-sdk` 当前无法访问（Network error 500），历史 README 中所有 SDK 链接均指向 `agiresearch/Cerebrum`，因此以 Cerebrum 为准；正式开发前需再确认一次该链接状态。

## 2. 关键事实：并发与 2.1x 性能声明的出处

- AIOS 基础论文 *AIOS: LLM Agent Operating System*（arXiv:2403.16971，https://arxiv.org/abs/2403.16971）已被 COLM 2025 接收（2025-07-08 News）。
- 赛题背景中"实测可达最高 2.1 倍性能提升"出自该论文的实验部分——通过智能体调度器对并发请求的调度与上下文切换优化获得。
- AIOS 内含调度器（Scheduler）模块，处理并发智能体请求的调度与上下文切换（README："scheduling, context switch, memory management, storage management, tool management, Agent SDK management"；实验性 Rust 重写 `aios-rs/` 中也列出 scheduler trait）。
- **这是我们"并发比串行快 ≥20%"指标的理论依托：同一套智能体流程，串行逐个执行 vs 交给 AIOS 并发调度，对比端到端墙钟时间。**

## 3. 环境与部署（官方 README 原文要点）

来源：https://github.com/agiresearch/AIOS 与 https://github.com/agiresearch/Cerebrum

- Python 版本：仅支持 **3.10 / 3.11**。
- 安装：克隆两仓库，`pip install -r requirements.txt`（CPU）或 `requirements-cuda.txt`（GPU），Cerebrum 用 `pip install -e .`；装 Kernel 时会自动装上 SDK（Local Kernel 模式下同一台机器装两者即可）。
- 启动 Kernel：`bash runtime/launch_kernel.sh`，或 `python3.x -m uvicorn runtime.launch:app --host 0.0.0.0 --port 8000`（FastAPI/uvicorn 服务）。
- 配置：`aios/config/config.yaml`（推荐直接改文件，避免环境变量同步问题）；CLI 有 `aios env list` / `aios env set` / `aios refresh`。
- 部署模式：Mode 1（本地 Kernel，开发+运行同机）→ Mode 2（远程 Kernel）→ Mode 2.5/3/4（规划中）。**比赛用 Mode 1 即可，最简、故障面最小。**

## 4. 端侧 7B/8B 模型接入（已验证的官方支持）

README "Configure LLM Models" 给出 config.yaml 示例（原文）：

```yaml
llms:
  models:
    # Ollama Models
    - name: "qwen2.5:7b"
      backend: "ollama"
      hostname: "http://localhost:11434"  # Make sure to run ollama server

    # vLLM Models
    - name: "meta-llama/Llama-3.1-8B-Instruct"
      backend: "vllm"
      hostname: "http://localhost:8091/v1"  # Make sure to run vllm server
```

- vLLM 启动：`vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8091`
- ollama 启动：先 `ollama pull qwen2.5:7b`
- 支持的 LLM 后端表：Anthropic / OpenAI / Deepseek / Google / Groq / HuggingFace / **ollama** / **vLLM** / Novita。开源模型的功能调用（function calling）自 2024-06-20 起支持（"Function calling for open-sourced LLMs (native huggingface, vLLM, ollama) is supported"）。
- Deepseek-r1 的 1.5b/7b/8b/... 已支持（2025-01-27 News）。

**选型结论：`vllm serve` 跑 Qwen2.5-7B-Instruct（或 Llama-3.1-8B-Instruct），backend: vllm 接入。** vLLM 的 continuous batching 使并发 LLM 请求真正并行处理，是"并发比串行快"的物理基础；ollama 作为无 GPU 环境的降级方案。

## 5. Cerebrum SDK 的智能体/工具开发方式（README 原文要点）

来源：https://github.com/agiresearch/Cerebrum

- 智能体目录结构（每个智能体一个文件夹）：

```
author_name/
└── agent_name/
      │── entry.py        # 智能体主逻辑
      │── config.json     # 配置与元数据（name/description/tools/meta/build）
      └── meta_requirements.txt  # 额外依赖
```

- config.json 的 `build` 字段指明入口文件与类名（如 `"entry": "agent.py", "module": "DemoAgent"`），`tools` 字段声明依赖工具。
- 运行单个智能体：`run-agent --mode local --agent_path <path> --task "<task_input>"`
- 工具（Tool）开发：`entry.py` 实现 `get_tool_call_format()`（OpenAI function-calling 格式）与 `run(params)` 两个方法；本地工具放 `cerebrum/tool/core/` 并在 `cerebrum/tool/core/registry.py` 注册；代码内加载：`AutoTool.from_preloaded("example/arxiv", local=False)`
- SDK 对外 API 分四类：**LLM APIs / Memory APIs / Storage APIs / Tool APIs**（细页在 docs.aios.foundation，见下）。
- 智能体间互调/消息路由、并发执行多智能体的具体 API 在 README 中未展开——**需要克隆仓库看 `cerebrum/example/` 与源码确认**（见第 7 节）。

## 6. 官方文档与生态入口

- 官方文档站：https://docs.aios.foundation/（GitBook；首页内容与 README 一致，含部署模式说明）
- AIOS Kernel 仓库：https://github.com/agiresearch/AIOS
- Cerebrum（AIOS SDK）仓库：https://github.com/agiresearch/Cerebrum
- 赛题指定论文：
  - AIOS: LLM Agent Operating System — https://arxiv.org/abs/2403.16971
  - Multi-Agent Collaboration Mechanisms: A Survey of LLMs — https://arxiv.org/pdf/2501.06322
- 赛题指定参考仓库（owl，Workforce 式多智能体协作的借鉴来源）：https://github.com/camel-ai/owl
- AgentHub / 应用入口：https://app.aios.foundation
- 支持的智能体框架（可 onboard 到 AIOS）：OpenAGI、AutoGen、Open-Interpreter、MetaGPT
- 相关论文：Cerebrum (AIOS SDK)（NAACL 2025）、A-MEM: Agentic Memory（arXiv:2502.12110）、LiteCUA 计算机使用智能体（arXiv:2505.18829）

## 7. 待克隆仓库后确认的点（占位，不算结论）

以下信息 README/文档首页未给出，须克隆两个仓库阅读源码与示例后回填，**当前不作为设计依据**：

1. `cerebrum/example/agents/` 下官方智能体的 entry.py 写法（Agent 基类、reply/执行入口、LLM 调用封装）；
2. 智能体间双向通信的实现方式（是否支持按 agent id 互调、消息路由/总线，还是需要在应用层自建 MessageBus）；
3. Kernel 调度器的并发模型与可观测性（请求队列、并发度参数、日志/trace 能力），影响性能对比实验的埋点方式；
4. `run-agent` 之外是否有多智能体编排入口（Workflow 类 API）；
5. 旧版 AIOS（v0.2 之前，`aios/hook/`、前端 WebUI）与新版 Kernel+Cerebrum 的功能对应关系，判断演示时用 Terminal UI / WebUI 还是自建 CLI 面板。

## 8. 对本赛题的直接启示

1. "AIOS-Agent SDK" = Cerebrum，智能体按 `entry.py + config.json` 规范开发，我们的 6 类智能体即 6 个符合该规范的智能体包，天然满足"在 AIOS 框架内"。
2. vLLM + 7B 的接入是官方一等公民，性能实验基础牢靠。
3. 2.1x 声明来自 AIOS 论文的调度实验，我们的 20% 指标只是它的保守下限，设计上应瞄准更高并给出分解分析。
4. 智能体通信与编排可能是 SDK 薄弱点，方案设计里自建轻量协作层（消息总线 + DAG 调度器）作为兜底，这在"操作系统"语境下反而是加分项（相当于给 AIOS 写了一个多智能体中间件）。
