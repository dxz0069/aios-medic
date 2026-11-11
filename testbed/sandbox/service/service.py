"""玩具关键服务：一个最小 HTTP 服务，供崩溃类故障（F04）与健康探针使用。

这是"被诊断系统"的一部分，故意保持简单：/health 返回 JSON 状态。
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

START_TS = time.time()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server 接口约定
        if self.path == "/health":
            body = json.dumps({
                "service": "toy-critical-service",
                "status": "ok",
                "pid": os.getpid(),
                "uptime_s": round(time.time() - START_TS, 1),
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):  # 静默访问日志，业务日志统一走 supervisor
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
