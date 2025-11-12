# WS 通信问题排查记录（待解决）

## 问题摘要

- **现象**：在 `main/xiaozhi-server/test/test_page.html` 中点击“连接”，浏览器多次提示 `WebSocket错误: 未知错误`，并立即断开连接。
- **影响范围**：所有通过测试页面（或任何仅携带查询参数的客户端）连接 `ws://192.168.31.166:8000/xiaozhi/v1/` 的请求。
- **错误状态**：客户端握手直接收到 `HTTP 500`，无法进入 WebSocket 会话阶段。

## 复现环境

- 服务器主机：`192.168.31.166`
- 相关服务端口：
  - `8000`：Python `xiaozhi-server` WebSocket
  - `8001`：`manager-web`
  - `8002`：`manager-api`
- Node / Python 服务均在本机启动，`python -m http.server 8006` 用于本地加载测试页面。

## 复现步骤

1. `cd main/xiaozhi-server/test`
2. 启动测试页静态服务器：
   ```bash
   /home/neousys/anaconda3/envs/xiaozhi-esp32-server/bin/python -m http.server 8006
   ```
3. 浏览器打开 `http://localhost:8006/test_page.html`
4. 点击页面上的“连接”按钮，观察日志。
5. 同时查看客户端与服务端输出。

## 实际现象

- 浏览器控制台持续出现以下日志：
  ```
  [6:07:22 PM.xxx] 正在连接: ws://192.168.31.166:8000/xiaozhi/v1/?device-id=...&client-id=web_test_client
  [6:07:22 PM.xxx] WebSocket错误: 未知错误
  [6:07:22 PM.xxx] 已断开连接
  ```
- 命令行复现（`curl` / `websockets.connect`）均返回 `HTTP 500`：
  ```
  websockets.exceptions.InvalidStatus: server rejected WebSocket connection: HTTP 500
  ```
- Python 服务标准日志 (`tmp/server.log` / `/tmp/xiaozhi_ws.log`) 仅显示初始化信息，没有任何异常或栈追踪。

## 期望行为

- 服务器应成功升级为 WebSocket 连接。
- 若鉴权失败，应返回自定义提示（如 `"认证失败"`），而非握手阶段直接抛出 `HTTP 500`。

## 现有线索

- 连接完全未建立，无法进入 `_handle_connection` 后续逻辑。
- `curl` 模拟 handshake 时返回：
  ```
  HTTP/1.1 500 Internal Server Error
  Failed to open a WebSocket connection. See server log for more information.
  ```
- `tmp/server.log` 未记录异常，说明错误发生在 logger 输出之前（握手阶段）。

## 代码排查

定位到 `core/websocket_server.py` 中 `_handle_connection` 的开头逻辑：

```python
headers = dict(websocket.request.headers)
if headers.get("device-id", None) is None:
    from urllib.parse import parse_qs, urlparse
    request_path = websocket.request.path
    ...
    websocket.request.headers["device-id"] = query_params["device-id"][0]
    ...
```

问题分析：

- `websocket.request.headers` 在 websockets 14.x 中是只读的 `Headers`（`CIMultiDictProxy`）对象。
- 代码试图直接写入 `device-id` / `client-id` / `authorization`，会触发 `TypeError: '...Proxy' object does not support item assignment`。
- 该异常未被捕获，被 websockets 框架转换为 `HTTP 500` 响应；由于未到 loguru 记录堆栈的流程，所以日志文件中没有任何错误信息。
- 即使客户端显式在请求头里带 `device-id`，由于 Header 名大小写问题（请求头会被规范化为 `Device-Id` 等），`headers.get("device-id")` 仍返回 `None`，导致同样的赋值语句被执行并抛错。

由此推断，本次 WebSocket 握手失败与签名/鉴权无关，而是由于服务端在握手阶段尝试修改只读 Header 触发异常。

## 实施的修复

1. **避免直接修改 `websocket.request.headers`**
   - 在 `_handle_connection` 中统一读取请求头并转换为小写字典，合并 URL 查询参数后存入 `websocket.merged_headers`。
   - `_handle_auth`、`ConnectionHandler` 全部改为读取 `merged_headers`，不再向只读 Header 回写。
2. **兼容 websockets>=14 的 `process_request` 参数**
   - `_http_response` 兼容 `Request` 对象，使用帮助方法读取 `Connection/Upgrade` 头，避免 `AttributeError`.
3. **配置与本地调试优化**
   - 本地调试时将 `data/.config.yaml` 设置 `read_config_from_api: false`，并清空 `manager-api.url/secret`，避免启动时请求 8002 导致连接拒绝。

## 验证过程

- 使用 `websockets.connect` 脚本直接发起握手，成功返回 101，连接可正常关闭。
- 通过 `python -m http.server 8006` 打开 `test_page.html`，将 OTA 地址指向本地 `http://127.0.0.1:8003/xiaozhi/ota/`，连接顺利完成、工具列表与 MCP 初始化正常。
- 文本消息 “你好” 能够收到 ASR 结果与 TTS 回传，服务端不再出现 `HTTP 500`，日志中无异常堆栈。

## 结论

- 问题根因是 websockets 14.x 下 Header 对象不可写导致的 TypeError。
- 通过合并 Header 的方式已消除异常，测试页面和脚本均验证通过。
- 若需要通过 manager-api 下发 OTA，可重新填写 `manager-api.url/secret`，否则保持本地配置即可。

## 后续待办

- [x] 修改 `core/websocket_server.py`，重构获取 `device-id / client-id / authorization` 的流程。
- [x] 验证并兼容 websockets>=14 的 `process_request` 接口。
- [x] 调整 `core/connection.py` 使用统一 Header。
- [x] 使用脚本与测试页面完成回归测试。
- [x] 在 `docs/0-服务器启动文档.md` 中补充调试提示。

> 备注：本文档已同步最终解决方案与验证结果，供后续升级依赖或排查类似问题参考。
