# ops/scnet — 郑州超算（SCNet）服务器运维脚本

> 同步约定：**凡在服务器上写好的脚本/配置，必须回同步到本目录**（服务器 `~/medic/` 是本目录的部署副本）。反向：本目录改动后用一条 scp 同步回服务器 `~/medic/`。

## 服务器信息（2026-11-11 开通）

- 入口：`ssh -i ~/.ssh/zz_key -p 65032 acotxxttog@zzeshell.scnet.cn` → 登录节点 zz-login02（Sugon OS）
- 算力：SothisAI Docker 容器实例，**海光 DCU 系 BW 卡（64GB 显存）**，16 核 / 60GB 内存，镜像 `pytorch2.9 + dtk26.04 + py3.11`
- **容器 72 小时销毁**：到期在新实例执行 `~/medic/x ~/medic/bootstrap.sh` 一键恢复（模型在 NFS 不用重下）

## 目录约定（NFS，跨容器持久）

| 路径 | 内容 |
|---|---|
| `~/models/Qwen2.5-7B-Instruct` | 模型权重（14.5GB，BF16）。**NFS 配额仅剩 ~3G，勿放大文件** |
| `~/aios-medic` | 仓库工作副本（本地 `git archive` 同步过去） |
| `~/medic` | 本目录部署副本（执行器 + bootstrap） |
| `~/bw_image_migration_20261107/proj4-devforge.tar` | 队友固化的环境镜像（含 `.venv`，aios-agent-sdk 0.0.3） |
| `~/proj4-reqs` | 队友 11 月初装环境的过程产物（requirements/脚本，勿动） |

## 脚本说明

| 脚本 | 用途 |
|---|---|
| `x` | **容器执行器**（登录节点用）：自动发现运行中的 Instances 作业，`srun --overlap + ai_docker exec` 进容器执行脚本。用法 `~/medic/x <脚本路径>`，超时用 `MEDIC_TIMEOUT=秒` |
| `bootstrap.sh` | **新容器一键恢复**：解压恢复 .venv → 启动推理服务(:8091, eager) → 三项健康检查 |
| `start_infer.sh` | 单独启动/重启推理服务 |
| `gpu_diag.sh` | GPU 分层诊断（env → matmul → sdpa → transformers eager 生成） |
| `probes/` | 历次一次性侦察/调试脚本（存档，可复用参考） |

## 已知坑（按踩中顺序）

1. **DTK torch 的 sdpa-flash 路径缺 cutlassFA 库**：`No matching libraries found for flash_attn_2_cuda*.so`（出自 `libtorch_hip.so` 的 cutlassfa_adapter）。**推理必须 `--attn eager`**；vLLM(DAS) wheel 自带 kernel 不受影响。
2. **`.venv` 的 torch 2.7.1 是 CUDA 版**：venv 只用于 AIOS/Cerebrum 服务（CPU 侧）；GPU 推理一律系统 python（torch 2.9.0+das.opt1.dtk2604）。
3. **登录节点频繁 SSH 会被限流**（connection reset）：合并为"单连接大脚本"，两次连接间留间隔；SSH 复用（ControlMaster）在该节点反而不稳。
4. **容器内无 Docker**：实验床沙箱不能起容器，F01-F05 需容器内直跑改造（F05 的 NET_ADMIN 待验证）。
5. **`tail` 是 toybox**：不支持 `-n 2`，用 `head`/`cat`/绝对路径 `/usr/bin/tail` 也一样报 `option used in invalid context`。
6. `python3 -m modelscope` 不可执行：新版本用 `modelscope download` CLI。
7. 容器内访问外网需 `source ~/.ai_user_info/ai_proxy`；github.com 不通（仓库同步走本机 `git archive | ssh tar`）。

## 待办

- [ ] vLLM(DAS) wheel：`vllm-0.11.0+das.opt1.dtk2604.cp311`，来源 [光合开发者社区](https://download.sourcefind.cn:65024/4/main/)（z-file 网页前端，需浏览器下载后传至 `~/medic/wheels/`）
- [ ] F05 网络故障注入需验证容器 NET_ADMIN 权限
- [ ] 与镜像"固化"方案二选一并更新本 README
