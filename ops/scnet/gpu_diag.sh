#!/bin/bash
cat > /tmp/gpu_diag.py << "PYEOF"
import os, traceback, glob
print("== env ==")
for k in ("DTK_HOME","ROCM_HOME","HIP_VISIBLE_DEVICES","LD_LIBRARY_PATH"):
    print(k, "=", os.environ.get(k))
print("flash so in dtk:", glob.glob("/opt/dtk/**/flash*", recursive=True)[:3])
print("flash pkg:", glob.glob("/usr/local/lib/python3.11/site-packages/flash*")[:3])
import torch
print("torch", torch.__version__, "cuda_avail", torch.cuda.is_available())
try:
    a = torch.randn(512, 512, device="cuda"); b = a @ a
    torch.cuda.synchronize(); print("MATMUL_OK", float(b.sum()))
except Exception:
    traceback.print_exc()
try:
    q = torch.randn(2, 8, 64, 32, device="cuda")
    o = torch.nn.functional.scaled_dot_product_attention(q, q, q)
    torch.cuda.synchronize(); print("SDPA_OK", tuple(o.shape))
except Exception:
    traceback.print_exc()
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    M = "/public/home/acotxxttog/models/Qwen2.5-7B-Instruct"
    tok = AutoTokenizer.from_pretrained(M)
    m = AutoModelForCausalLM.from_pretrained(M, torch_dtype=torch.bfloat16, attn_implementation="eager").cuda()
    inp = tok(["给我一个JSON"], return_tensors="pt").to("cuda")
    out = m.generate(**inp, max_new_tokens=10)
    print("GEN_OK", tok.decode(out[0]))
except Exception:
    traceback.print_exc()
PYEOF
python3 /tmp/gpu_diag.py 2>&1 | grep -vE "^\s*$|Loading checkpoint" | head -50
