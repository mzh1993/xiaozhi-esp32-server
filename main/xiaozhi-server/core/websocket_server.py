import asyncio
import json

import websockets
from config.logger import setup_logging
from core.connection import ConnectionHandler
from config.config_loader import get_config_from_api
from core.auth import AuthManager, AuthenticationError
from core.utils.modules_initialize import initialize_modules
from core.utils.util import check_vad_update, check_asr_update

TAG = __name__


class WebSocketServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.config_lock = asyncio.Lock()
        modules = initialize_modules(
            self.logger,
            self.config,
            "VAD" in self.config["selected_module"],
            "ASR" in self.config["selected_module"],
            "LLM" in self.config["selected_module"],
            False,
            "Memory" in self.config["selected_module"],
            "Intent" in self.config["selected_module"],
        )
        self._vad = modules["vad"] if "vad" in modules else None
        self._asr = modules["asr"] if "asr" in modules else None
        self._llm = modules["llm"] if "llm" in modules else None
        self._intent = modules["intent"] if "intent" in modules else None
        self._memory = modules["memory"] if "memory" in modules else None

        self.active_connections = set()

        auth_config = self.config["server"].get("auth", {})
        self.auth_enable = auth_config.get("enabled", False)
        # 设备白名单
        self.allowed_devices = set(auth_config.get("allowed_devices", []))
        secret_key = self.config["server"]["auth_key"]
        expire_seconds = auth_config.get("expire_seconds", None)
        self.auth = AuthManager(secret_key=secret_key, expire_seconds=expire_seconds)

    async def start(self):
        server_config = self.config["server"]
        host = server_config.get("ip", "0.0.0.0")
        port = int(server_config.get("port", 8000))

        async with websockets.serve(
            self._handle_connection, host, port, process_request=self._http_response
        ):
            await asyncio.Future()

    async def _handle_connection(self, websocket):
        try:
            from urllib.parse import parse_qs, urlparse

            # websockets>=12 将 request.headers 暴露为不可变对象，统一转换为小写字典
            merged_headers = {k.lower(): v for k, v in websocket.request.headers.items()}

            device_id = merged_headers.get("device-id")
            client_id = merged_headers.get("client-id")
            authorization = merged_headers.get("authorization")

            request_path = websocket.request.path or ""
            parsed_url = urlparse(request_path)
            query_params = parse_qs(parsed_url.query)

            if not device_id:
                device_id = query_params.get("device-id", [None])[0]
            if not device_id:
                await websocket.send("端口正常，如需测试连接，请使用test_page.html")
                await websocket.close()
                return

            if not client_id:
                client_id = query_params.get("client-id", [None])[0]
            if not authorization:
                authorization = query_params.get("authorization", [None])[0]

            merged_headers["device-id"] = device_id
            if client_id:
                merged_headers["client-id"] = client_id
            if authorization:
                merged_headers["authorization"] = authorization

            # 挂载到 websocket 对象，供认证 & ConnectionHandler 使用
            setattr(websocket, "merged_headers", merged_headers)

        except Exception as exc:
            self.logger.bind(tag=TAG).error(f"握手阶段解析连接信息失败: {exc}")
            await websocket.close()
            return

        """处理新连接，每次创建独立的ConnectionHandler"""
        # 先认证，后建立连接
        try:
            await self._handle_auth(websocket)
        except AuthenticationError:
            await websocket.send("认证失败")
            await websocket.close()
            return
        # 创建ConnectionHandler时传入当前server实例
        handler = ConnectionHandler(
            self.config,
            self._vad,
            self._asr,
            self._llm,
            self._memory,
            self._intent,
            self,  # 传入server实例
        )
        self.active_connections.add(handler)
        try:
            await handler.handle_connection(websocket)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理连接时出错: {e}")
        finally:
            # 确保从活动连接集合中移除
            self.active_connections.discard(handler)
            # 强制关闭连接（如果还没有关闭的话）
            try:
                # 安全地检查WebSocket状态并关闭
                if hasattr(websocket, "closed") and not websocket.closed:
                    await websocket.close()
                elif hasattr(websocket, "state") and websocket.state.name != "CLOSED":
                    await websocket.close()
                else:
                    # 如果没有closed属性，直接尝试关闭
                    await websocket.close()
            except Exception as close_error:
                self.logger.bind(tag=TAG).error(
                    f"服务器端强制关闭连接时出错: {close_error}"
                )

    async def _http_response(self, path, request_headers):
        # 兼容 websockets>=14 将 Request 对象传入的情况
        headers_obj = getattr(request_headers, "headers", request_headers)
        def header_get(name, default=""):
            value = headers_obj.get(name, default)
            return value or default

        connection_header = header_get("Connection")
        upgrade_header = header_get("Upgrade")
        if "upgrade" in connection_header.lower() and upgrade_header.lower() == "websocket":
            return None

        body = b"Server is running\n"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ]
        return (200, headers, body)

    async def update_config(self) -> bool:
        """更新服务器配置并重新初始化组件

        Returns:
            bool: 更新是否成功
        """
        try:
            async with self.config_lock:
                # 重新获取配置
                new_config = get_config_from_api(self.config)
                if new_config is None:
                    self.logger.bind(tag=TAG).error("获取新配置失败")
                    return False
                self.logger.bind(tag=TAG).info(f"获取新配置成功")
                # 检查 VAD 和 ASR 类型是否需要更新
                update_vad = check_vad_update(self.config, new_config)
                update_asr = check_asr_update(self.config, new_config)
                self.logger.bind(tag=TAG).info(
                    f"检查VAD和ASR类型是否需要更新: {update_vad} {update_asr}"
                )
                # 更新配置
                self.config = new_config
                # 重新初始化组件
                modules = initialize_modules(
                    self.logger,
                    new_config,
                    update_vad,
                    update_asr,
                    "LLM" in new_config["selected_module"],
                    False,
                    "Memory" in new_config["selected_module"],
                    "Intent" in new_config["selected_module"],
                )

                # 更新组件实例
                if "vad" in modules:
                    self._vad = modules["vad"]
                if "asr" in modules:
                    self._asr = modules["asr"]
                if "llm" in modules:
                    self._llm = modules["llm"]
                if "intent" in modules:
                    self._intent = modules["intent"]
                if "memory" in modules:
                    self._memory = modules["memory"]
                self.logger.bind(tag=TAG).info(f"更新配置任务执行完毕")
                return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"更新服务器配置失败: {str(e)}")
            return False

    async def _handle_auth(self, websocket):
        # 先认证，后建立连接
        if self.auth_enable:
            headers = getattr(
                websocket,
                "merged_headers",
                {k.lower(): v for k, v in websocket.request.headers.items()},
            )
            device_id = headers.get("device-id")
            client_id = headers.get("client-id")
            if self.allowed_devices and device_id in self.allowed_devices:
                # 如果属于白名单内的设备，不校验token，直接放行
                return
            else:
                # 否则校验token
                token = headers.get("authorization", "")
                if token.startswith("Bearer "):
                    token = token[7:]  # 移除'Bearer '前缀
                else:
                    raise AuthenticationError("Missing or invalid Authorization header")
                # 进行认证
                auth_success = self.auth.verify_token(
                    token, client_id=client_id, username=device_id
                )
                if not auth_success:
                    raise AuthenticationError("Invalid token")
