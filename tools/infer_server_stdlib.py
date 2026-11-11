#!/usr/bin/env python3
"""OpenAI 兼容推理服务（纯标准库，无 fastapi 依赖）——DCU/BW 过渡方案。

用途：在 vLLM(DCU 版) 就绪前，为 Spike ① 与开发提供 /v1/chat/completions 端点。
限制：生成单流串行（互斥锁），不支持 continuous batching——并发性能实验仍以 vLLM 为准。
端点：POST /v1/chat/completions、GET /v1/models、GET /health

用法（容器内）:
  python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5-7B-Instruct --port 8091
"""
import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from transformers import AutoModelForCausalLM, AutoTokenizer


class InferEngine:
    def __init__(self, model_path: str, dtype: str, attn: str = "sdpa"):
        import torch
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=getattr(torch, dtype),
                attn_implementation=attn, trust_remote_code=True
            ).cuda()
        except Exception:  # noqa: BLE001 - DTK 上 sdpa/flash 探测可能失败，降级 eager
            print(f"attn_implementation={attn} failed, fallback to eager", flush=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=getattr(torch, dtype),
                attn_implementation="eager", trust_remote_code=True
            ).cuda()
        self.model.eval()
        self.lock = threading.Lock()

    def chat(self, messages, temperature, max_tokens):
        with self.lock:
            text = self.tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tok([text], return_tensors="pt").to(self.model.device)
            do_sample = float(temperature) > 0
            kwargs = dict(max_new_tokens=int(max_tokens), do_sample=do_sample)
            if do_sample:
                kwargs.update(temperature=float(temperature), top_p=0.9)
            t0 = time.time()
            with self.torch.no_grad():
                out = self.model.generate(**inputs, **kwargs)
            gen = out[0][inputs["input_ids"].shape[1]:]
            return self.tok.decode(gen, skip_special_tokens=True), time.time() - t0, len(gen)


ENGINE = None


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
                "_elapsed_s": round(elapsed, 2)})
        except Exception as e:  # noqa: BLE001 - 服务需兜底返回错误
            self._json(500, {"error": {"message": str(e)}})

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}", flush=True)


ENGINE_ID = "qwen2.5-7b-instruct"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    ap.add_argument("--attn", default="sdpa", choices=["sdpa", "eager", "flash_attention_2"])
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    global ENGINE
    print(f"loading model from {args.model} ({args.dtype}, attn={args.attn}) ...", flush=True)
    t0 = time.time()
    ENGINE = InferEngine(args.model, args.dtype, args.attn)
    print(f"model loaded in {time.time()-t0:.1f}s, serving on {args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
