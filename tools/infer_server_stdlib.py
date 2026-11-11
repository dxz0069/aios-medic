#!/usr/bin/env python3
"""OpenAI 兼容推理服务（纯标准库）——DCU/BW 过渡方案，含微批处理。

- 端点：POST /v1/chat/completions、GET /v1/models、GET /health
- **微批处理**：批量窗口内聚合并发请求，transformers 批量生成（continuous
  batching 的简化前体）——使并发调度模式在 vLLM(DAS) 就绪前即有真实墙钟收益。
- 限制：无 tool-call 支持；DTK 环境需 --attn eager（sdpa-flash 缺 cutlassFA 库）。

用法（容器内）:
  python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5-7B-Instruct \
      --port 8091 --attn eager
"""
import argparse
import json
import queue as _queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from transformers import AutoModelForCausalLM, AutoTokenizer


class _Job:
    __slots__ = ("messages", "temperature", "max_tokens", "event", "result")

    def __init__(self, messages, temperature, max_tokens):
        self.messages, self.temperature, self.max_tokens = messages, temperature, max_tokens
        self.event = threading.Event()
        self.result = None  # (content, elapsed_s, ntok) 或 Exception


class InferEngine:
    def __init__(self, model_path: str, dtype: str, attn: str = "sdpa",
                 batch_window_ms: int = 300, max_batch: int = 8):
        import torch
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=getattr(torch, dtype),
                attn_implementation=attn, trust_remote_code=True).cuda()
        except Exception:  # noqa: BLE001 - DTK 上 sdpa/flash 探测可能失败，降级 eager
            print(f"attn_implementation={attn} failed, fallback to eager", flush=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=getattr(torch, dtype),
                attn_implementation="eager", trust_remote_code=True).cuda()
        self.model.eval()

        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self._q: _queue.Queue = _queue.Queue()
        self.batch_window_ms, self.max_batch = batch_window_ms, max_batch
        threading.Thread(target=self._batcher, daemon=True).start()

    def _batcher(self):
        while True:
            jobs = [self._q.get()]
            deadline = time.time() + self.batch_window_ms / 1000.0
            while len(jobs) < self.max_batch:
                remain = deadline - time.time()
                if remain <= 0:
                    break
                try:
                    jobs.append(self._q.get(timeout=remain))
                except _queue.Empty:
                    break
            self._run_batch(jobs)

    def _run_batch(self, jobs):
        try:
            texts = [self.tok.apply_chat_template(j.messages, tokenize=False,
                                                  add_generation_prompt=True) for j in jobs]
            inputs = self.tok(texts, return_tensors="pt", padding=True).to(self.model.device)
            temps = [float(j.temperature or 0.0) for j in jobs]
            do_sample = any(t > 0 for t in temps)
            kwargs = dict(max_new_tokens=max(int(j.max_tokens) for j in jobs),
                          do_sample=do_sample)
            if do_sample:
                kwargs.update(temperature=max(0.05, max(temps)), top_p=0.9)
            t0 = time.time()
            with self.torch.no_grad():
                out = self.model.generate(**inputs, **kwargs)
            gen = out[:, inputs["input_ids"].shape[1]:]
            elapsed = round(time.time() - t0, 2)
            for i, j in enumerate(jobs):
                content = self.tok.decode(gen[i], skip_special_tokens=True)
                j.result = (content, elapsed, int(gen[i].shape[0]))
            for j in jobs:
                j.event.set()
        except Exception as e:  # noqa: BLE001 - 单批失败不能杀死批处理线程
            print(f"[batch-error] {e}", flush=True)
            for j in jobs:
                j.result = RuntimeError(str(e))
                j.event.set()

    def chat(self, messages, temperature, max_tokens):
        job = _Job(messages, temperature, max_tokens)
        self._q.put(job)
        job.event.wait()
        if isinstance(job.result, Exception):
            raise job.result
        return job.result


ENGINE = None
ENGINE_ID = "qwen2.5-7b-instruct"


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/v1/models":
            self._json(200, {"object": "list", "data": [{"id": ENGINE_ID, "object": "model"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/v1/chat/completions":
            return self._json(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            content, elapsed, ntok = ENGINE.chat(
                req.get("messages", []), req.get("temperature", 0.1),
                req.get("max_tokens", 512))
            self._json(200, {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
                "created": int(time.time()), "model": req.get("model", ENGINE_ID),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": ntok, "total_tokens": ntok},
                "_elapsed_s": elapsed})
        except Exception as e:  # noqa: BLE001 - 服务需兜底返回错误
            self._json(500, {"error": {"message": str(e)}})

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    ap.add_argument("--attn", default="sdpa", choices=["sdpa", "eager", "flash_attention_2"])
    ap.add_argument("--batch-window-ms", type=int, default=300)
    ap.add_argument("--max-batch", type=int, default=8)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    global ENGINE
    print(f"loading model from {args.model} ({args.dtype}, attn={args.attn}, "
          f"batch_window={args.batch_window_ms}ms max_batch={args.max_batch}) ...", flush=True)
    t0 = time.time()
    ENGINE = InferEngine(args.model, args.dtype, args.attn,
                         args.batch_window_ms, args.max_batch)
    print(f"model loaded in {time.time()-t0:.1f}s, serving on {args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
