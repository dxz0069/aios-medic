"""F02 磁盘写满：向受限 tmpfs /var/scratch 持续写入 64MB 块直至 ENOSPC。

安全边界：目标目录以 --tmpfs size=300m 挂载，写满不影响容器根文件系统。
证据链：df /var/scratch 水位 + 应用写入 ENOSPC 报错（supervisor/服务日志）。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f02"
SCRATCH = Path("/var/scratch")
CHUNK = 64 * 1024 * 1024


def fill_dir() -> Path:
    return SCRATCH / "fill"


def run(action: str) -> int:
    if action == "status":
        st = os.statvfs(SCRATCH)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used_pct = round((total - free) / total * 100, 1) if total else -1
        print(f"{NAME}: scratch total={total >> 20}MB free={free >> 20}MB used={used_pct}% files={len(list(fill_dir().glob('*')))}")
        return 0
    if action == "clear":
        removed = 0
        for f in fill_dir().glob("fill.chunk.*"):
            f.unlink()
            removed += 1
        print(f"{NAME}: cleared ({removed} chunks removed)")
        return 0
    if action == "inject":
        d = fill_dir()
        d.mkdir(parents=True, exist_ok=True)
        n = len(list(d.glob("fill.chunk.*")))
        wrote = 0
        try:
            while True:
                with open(d / f"fill.chunk.{n}", "wb") as f:
                    f.write(b"\0" * CHUNK)
                n += 1
                wrote += 1
        except OSError as e:
            print(f"{NAME}: injected, {wrote} chunks written, stopped at ENOSPC ({e.errno})")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
