"""
飞书机器人启动入口（含 lark_channel 兼容性补丁）。

补丁说明：
  lark_channel 库的同步 HTTP Transport 在发送 JSON POST 请求时
  未设置 Content-Type: application/json 头，导致飞书开放平台
  返回 10003 invalid param。此补丁在请求头中自动补充该字段。
"""

# ---- 补丁：必须在 lark_channel 发起任何 HTTP 请求前应用 ----
import lark_channel.core.http.transport as _transport

_original_build_header = _transport._build_header


def _patched_build_header(request, option, conf=None):
    headers = _original_build_header(request, option, conf)
    if request.body is not None and not any(
        k.lower() == "content-type" for k in headers
    ):
        headers["Content-Type"] = "application/json"
    return headers


_transport._build_header = _patched_build_header
# ---- 补丁结束 ----

from feishu_bot.bot import run

if __name__ == "__main__":
    run()
