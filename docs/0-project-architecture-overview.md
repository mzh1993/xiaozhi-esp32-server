## 小智后端服务 xiaozhi-esp32-server 架构总览

本文帮助你快速理解本项目的整体框架、目录结构、关键组件及其职责、运行时拓扑与常用入口，便于快速定位代码与配置位置。建议配合根目录 `README.md`、`README_en.md` 与 `docs/` 下各专题文档一起阅读。

---

### 一、总体结构与职责映射

- **根仓库（单体多模块）**：包含 Python 实时服务、Java 管理端 API、Web/H5 管理端与移动端、部署脚本与说明文档。
  - `main/xiaozhi-server`（Python 核心服务）
    - 核心对话/多模态管线、ASR/TTS/LLM/VLLM 集成、MCP/IOT 工具调用、插件系统、测试工具、Docker 编排与配置。
  - `main/manager-api`（Java 后端）
    - 提供“智控台”管理能力（用户、设备、系统配置、指令下发、数据存储等）。
  - `main/manager-web`（Web 管理端）
    - Vue Web 前端的“智控台”界面。
  - `main/manager-mobile`（移动端 H5/多端）
    - 移动端“智控台”界面与适配。
  - `docs`（文档与部署）
    - 部署、集成、测试、FAQ、示例配置与图片资源。
  - 顶层 Dockerfile 与脚本
    - 服务器镜像、Web 镜像、基础镜像构建与一键脚本。

---

### 二、运行时拓扑（高层）

1) 设备侧（ESP32 等）<—MQTT/UDP/WebSocket—> 2) Python 服务（`xiaozhi-server`）

- Python 服务内：
  - VAD/ASR 语音识别（可本地 FunASR/Sherpa 或 API）
  - LLM 推理（OpenAI 兼容接口：阿里百炼、豆包、智谱、DeepSeek、Gemini、Ollama、Dify、FastGPT 等）
  - VLLM 视觉模型（OpenAI 兼容接口：GLM-4V、Qwen2.5-VL 等）
  - TTS 语音合成（本地与云服务、支持流式/双流式）
  - MCP/IOT/插件化工具调用与指令路由
  - 记忆（本地短期或 mem0ai）

3) 管理面（“智控台”）：

- `manager-api` 提供 API，`manager-web`/`manager-mobile` 作为前端 UI
- 通过 MQTT 将 MCP 指令下发至设备；管理用户/设备/配置；查看状态

4) 数据与配置：

- “最简化安装”：主要使用配置文件存储
- “全模块安装”：Java 管理端 + 数据库

详细部署方式、资源需求与推荐组合：见根目录 `README.md` 的“部署文档/配置说明”，以及 `docs/Deployment.md` 与 `docs/Deployment_all.md`。

---

### 三、目录地图与定位指南

#### 3.1 根目录结构

- `Dockerfile-server` / `Dockerfile-server-base` / `Dockerfile-web`：Docker 镜像构建文件
- `docker-setup.sh`：一键构建/运行脚本
- `README.md` / `README_en.md`：项目概览、部署选型、能力矩阵、测试入口
- `docs/`：专题文档（MQTT 网关、MCP、视觉、语音等）与部署说明

#### 3.2 Python 服务：`main/xiaozhi-server`

**入口与编排：**
- ```1:144:main/xiaozhi-server/app.py```：服务主入口，启动 WebSocket 和 HTTP 服务器，初始化认证密钥
- `docker-compose.yml` / `docker-compose_all.yml`：Docker Compose 编排（简化/全模块）

**配置管理：**
- `config/settings.py`：配置检查与验证
- `config/config_loader.py`：配置文件加载与合并顺序（支持本地配置和 API 配置）
- `config.yaml` / `config_from_api.yaml`：运行时配置（模型选择、密钥、端口等）
- `mcp_server_settings.json`：MCP 接入点相关配置
- `config/logger.py`：日志系统初始化
- `config/manage_api_client.py`：管理端 API 客户端（用于设备绑定、配置同步等）

**模型与资源：**
- `models/`：本地模型文件（FunASR、SileroVAD 等）
- `config/assets/`：音频资源（绑定码提示音、唤醒词等）
- `music/`：背景音乐文件

**核心逻辑目录：`core/`**

**服务层：**
- ```15:54:main/xiaozhi-server/core/websocket_server.py```：WebSocket 服务器，管理连接生命周期，初始化 VAD/ASR/LLM/Memory/Intent 模块
- ```54:1147:main/xiaozhi-server/core/connection.py```：`ConnectionHandler` 类，每个设备连接一个实例，管理会话状态、音频队列、工具调用等
- `core/http_server.py`：HTTP 服务器（OTA、视觉分析等接口）
- `core/auth.py`：JWT 认证管理

**消息处理：`core/handle/`**
- ```13:91:main/xiaozhi-server/core/handle/receiveAudioHandle.py```：接收音频消息处理（VAD 检测、唤醒处理、开始对话）
- ```11:260:main/xiaozhi-server/core/handle/sendAudioHandle.py```：发送音频消息处理（TTS 流式发送、流控、MQTT 头部封装）
- `core/handle/textHandle.py`：文本消息处理入口
- `core/handle/textMessageHandler.py`：文本消息处理器抽象基类
- `core/handle/textMessageHandlerRegistry.py`：消息处理器注册表
- `core/handle/textMessageProcessor.py`：消息路由与分发
- `core/handle/textHandler/`：各类文本消息处理器（hello、listen、iot、mcp、server 等）
- `core/handle/intentHandler.py`：意图识别处理
- `core/handle/reportHandle.py`：ASR/TTS 上报处理（用于全模块安装的聊天历史记录）
- `core/handle/abortHandle.py`：打断处理

**AI 模型提供者：`core/providers/`**

**ASR（语音识别）：`core/providers/asr/`**
- `base.py`：ASR 基类，定义音频队列、优先级线程、接收接口
- `fun_local.py`：FunASR 本地实现（支持 GPU）
- `fun_server.py`：FunASR 服务端调用
- `sherpa_onnx_local.py`：Sherpa-ONNX 本地实现
- `doubao.py` / `doubao_stream.py`：火山引擎豆包 ASR（非流式/流式）
- `aliyun.py` / `aliyun_stream.py`：阿里云 ASR
- `tencent.py`：腾讯云 ASR
- `baidu.py`：百度 ASR
- `openai.py`：OpenAI Whisper
- `xunfei_stream.py`：讯飞流式 ASR
- `qwen3_asr_flash.py`：千问 ASR Flash
- `vosk.py`：Vosk 本地识别

**TTS（语音合成）：`core/providers/tts/`**
- `base.py`：TTS 基类，定义流式/非流式接口
- `default.py`：默认 TTS（用于绑定阶段）
- **流式 TTS：**
  - `huoshan_double_stream.py`：火山双流式（推荐）
  - `aliyun_stream.py`：阿里云流式
  - `linkerai.py`：灵犀流式（免费）
  - `index_stream.py`：Index-TTS 流式
  - `minimax_httpstream.py`：MiniMax HTTP 流式
- **非流式 TTS：**
  - `doubao.py`、`aliyun.py`、`tencent.py`、`edge.py`、`openai.py` 等
- **本地 TTS：**
  - `fishspeech.py`：FishSpeech
  - `gpt_sovits_v2.py` / `gpt_sovits_v3.py`：GPT-SoVITS
  - `paddle_speech.py`：PaddleSpeech
  - `ttson.py`、`siliconflow.py`、`custom.py` 等

**LLM（大语言模型）：`core/providers/llm/`**
- `base.py`：LLM 基类，定义 OpenAI 兼容接口
- `openai.py`：OpenAI 标准实现（用于所有 OpenAI 兼容平台）
- `AliBL/`：阿里百炼
- `ollama/`：Ollama 本地模型
- `dify/`、`fastgpt/`、`coze/`、`xinference/`、`homeassistant/`：各平台适配
- `gemini/`：Google Gemini
- `system_prompt.py`：系统提示词管理

**VLLM（视觉大模型）：`core/providers/vllm/`**
- `base.py`：视觉模型基类
- `openai.py`：OpenAI 兼容实现（GLM-4V、Qwen2.5-VL 等）

**Intent（意图识别）：`core/providers/intent/`**
- `base.py`：意图识别基类
- `function_call/function_call.py`：Function Call 实现（推荐，速度快效果好）
- `intent_llm/`：通过 LLM 识别意图
- `nointent/`：无意图模式

**Memory（记忆）：`core/providers/memory/`**
- `base.py`：记忆基类
- `mem_local_short/`：本地短期记忆（总结功能）
- `mem0ai/`：mem0ai 接口记忆
- `nomem/`：无记忆模式

**VAD（语音活动检测）：`core/providers/vad/`**
- `base.py`：VAD 基类
- `silero.py`：Silero VAD 实现

**工具调用：`core/providers/tools/`**
- ```1:125:main/xiaozhi-server/core/providers/tools/unified_tool_manager.py```：统一工具管理器，管理所有类型的工具（设备 IOT、MCP、插件等）
- `unified_tool_handler.py`：统一工具处理器，执行工具调用
- `base/`：工具基类定义
- `device_iot/`：设备 IOT 协议工具
- `device_mcp/`：设备 MCP 协议工具
- `server_mcp/`：服务端 MCP 协议工具
- `mcp_endpoint/`：MCP 接入点工具
- `server_plugins/`：服务端插件工具

**API 接口：`core/api/`**
- `base_handler.py`：API 处理器基类
- `ota_handler.py`：OTA 固件更新接口
- `vision_handler.py`：视觉分析接口

**工具类：`core/utils/`**
- `modules_initialize.py`：模块初始化（VAD/ASR/LLM/TTS/Memory/Intent）
- `dialogue.py`：对话历史管理
- `prompt_manager.py`：提示词增强管理
- `voiceprint_provider.py`：声纹识别提供者
- `cache/`：缓存管理（配置缓存等）
- `asr.py`、`tts.py`、`llm.py`、`vllm.py`、`vad.py`、`memory.py`、`intent.py`：各模块工具函数
- `util.py`：通用工具函数
- `textUtils.py`：文本处理工具
- `output_counter.py`：输出字数限制检查

**插件系统：`plugins_func/`**
- `loadplugins.py`：自动导入插件模块
- `register.py`：插件注册与 Action 响应
- `functions/`：服务端插件函数集合
  - `get_weather.py`：天气查询
  - `get_time.py`：时间查询
  - `get_news_from_chinanews.py` / `get_news_from_newsnow.py`：新闻获取
  - `play_music.py`：播放音乐
  - `hass_*.py`：HomeAssistant 集成
  - `change_role.py`：角色切换
  - `handle_exit_intent.py`：退出意图处理

**测试工具：**
- `performance_tester.py`：性能测试入口脚本
- `performance_tester/`：各模块性能测试脚本
  - `performance_tester_asr.py`、`performance_tester_stream_asr.py`
  - `performance_tester_llm.py`
  - `performance_tester_tts.py`、`performance_tester_stream_tts.py`
  - `performance_tester_vllm.py`
- `test/`：前端测试工具
  - `test_page.html`：音频交互测试页面（Chrome 浏览器打开）
  - `js/`：WebSocket 客户端、Opus 编解码等 JS 库

#### 3.3 Java 管理端：`main/manager-api`

**项目结构：**
- `pom.xml`：Maven 依赖管理与构建配置

**源码目录：`src/main/java/xiaozhi/`**

**主入口：**
- ```1:13:main/manager-api/src/main/java/xiaozhi/AdminApplication.java```：Spring Boot 应用入口

**通用模块：`common/`**
- `annotation/`：自定义注解（数据过滤、日志操作等）
- `aspect/`：AOP 切面（Redis 缓存等）
- `config/`：配置类（异步、MyBatis Plus、RestTemplate、Swagger 等）
- `constant/`：常量定义
- `dao/`、`entity/`、`service/`：基础 DAO、实体、服务
- `exception/`：异常处理（全局异常处理器）
- `interceptor/`：拦截器（数据过滤、权限等）
- `page/`：分页与 Token DTO
- `redis/`：Redis 配置与工具
- `user/`：用户详情
- `utils/`：工具类集合
- `validator/`：参数校验
- `xss/`：XSS 防护

**业务模块：`modules/`**

**设备管理：`device/`**
- `controller/DeviceController.java`：设备管理接口（绑定、在线状态、MQTT 转发）
- ```495:550:main/manager-api/src/main/java/xiaozhi/modules/device/service/impl/DeviceServiceImpl.java```：设备服务实现（MQTT 配置生成、设备绑定等）
- `controller/OTAController.java`：OTA 固件更新接口
- `dao/`、`dto/`、`entity/`、`vo/`：数据访问层、数据传输对象、实体、视图对象

**智能体管理：`agent/`**
- `controller/`：智能体相关接口（模板、插件映射、聊天历史等）
- `service/AgentMcpAccessPointServiceImpl.java`：MCP 接入点服务
- `dao/`、`dto/`、`entity/`、`vo/`、`Enums/`：相关数据层

**系统管理：`sys/`**
- `controller/`：用户、角色、权限、参数管理等接口
- `controller/ServerSideManageController.java`：服务端管理接口（通过 WebSocket 下发服务端动作）
- `service/`、`dao/`：服务层与数据访问层

**模型配置：`model/`**
- 模型提供者与模型配置管理

**安全模块：`security/`**
- Spring Security 配置、JWT 认证、权限控制等

**其他模块：**
- `sms/`：短信服务
- `timbre/`：音色管理
- `voiceclone/`：语音克隆
- `config/`：系统配置初始化

**资源目录：`src/main/resources/`**
- `application.yml` / `application-dev.yml`：应用配置
- `db/changelog/`：数据库迁移脚本（Liquibase）
- `mapper/`：MyBatis XML 映射文件
- `i18n/`：国际化资源文件（中英文、繁简）
- `lua/`：Redis Lua 脚本
- `logback-spring.xml`：日志配置

**职责总结：**
- 用户、设备、智能体管理
- MQTT 配置生成与指令下发
- 系统参数、字典、权限管理
- 聊天历史记录（全模块安装）
- OTA 固件更新管理
- 模型配置管理
- API 网关与认证

#### 3.4 Web 管理端：`main/manager-web`

**技术栈：** Vue.js + Vue Router + Vuex + Element UI

**目录结构：**
- `src/apis/`：API 接口封装
  - `api.js`、`httpRequest.js`：HTTP 请求封装
  - `module/`：各模块 API（admin、agent、device、model、ota、user 等）
- `src/components/`：公共组件
  - `AddDeviceDialog.vue`、`DeviceItem.vue`：设备管理
  - `AddModelDialog.vue`、`ModelEditDialog.vue`：模型配置
  - `VoicePrintDialog.vue`、`VoiceCloneDialog.vue`：语音相关
  - `ChatHistoryDialog.vue`：聊天历史
  - `AudioPlayer.vue`：音频播放器
  - 等 24 个组件
- `src/views/`：页面视图
  - `home.vue`：首页
  - `login.vue`、`register.vue`：登录注册
  - `DeviceManagement.vue`：设备管理
  - `ModelConfig.vue`：模型配置
  - `UserManagement.vue`：用户管理
  - `AgentTemplateManagement.vue`：智能体模板管理
  - `OtaManagement.vue`：OTA 管理
  - 等 19 个页面
- `src/router/`：路由配置
- `src/store/`：Vuex 状态管理
- `src/i18n/`：国际化（中英文、繁简）
- `src/utils/`：工具函数
- `public/`：静态资源（含 PWA Service Worker）

#### 3.5 移动端：`main/manager-mobile`

**技术栈：** Uni-App + TypeScript + Vite

**目录结构：**
- `src/api/`：API 接口封装（agent、device、voiceprint、chat-history 等）
- `src/pages/`：页面
  - `index/`：首页
  - `login/`、`register/`、`forgot-password/`：认证相关
  - `device/`、`device-config/`：设备管理与配置
  - `agent/`：智能体管理
  - `chat-history/`：聊天历史
  - `voiceprint/`：声纹识别
  - `settings/`：设置
- `src/layouts/`：布局组件（TabBar 等）
- `src/components/`：公共组件
- `src/store/`：状态管理（Pinia）
- `src/i18n/`：国际化
- `src/http/`：HTTP 请求封装（Alova）
- `pages.json`、`manifest.json`：页面配置与打包配置

---

### 四、关键能力到代码位置的“速查表”

- **流式语音对话（ASR→LLM→TTS）**：`main/xiaozhi-server/core/` 下的 `asr/`、`pipeline/`、`tts/`、`llm/`，入口 `app.py`
- **MCP 接入与指令下发**：
  - Python 端 MCP/工具：`main/xiaozhi-server/core/mcp/`、`plugins_func/`
  - 管理端下发（MQTT）：`main/manager-api`（配合 `docs/mqtt-gateway-integration.md`）
- **视觉感知（VLLM）**：`main/xiaozhi-server/core/vllm/`，详见 `docs/mcp-vision-integration.md`
- **声纹识别**：`main/xiaozhi-server/core/voiceprint/`（目录命名以实际仓库为准），文档见 `docs/voiceprint-integration.md`
- **配置与切换（免费/流式/厂商）**：`main/xiaozhi-server/config/*.py|yaml` + 根 `README.md` 配置推荐表
- **性能测试入口**：`main/xiaozhi-server/performance_tester.py` 与 `performance_tester/`
- **音频交互测试页**：`main/xiaozhi-server/test/test_page.html`

---

### 五、部署与环境

- 最简化安装（仅 Python 服务）

  - 参考：`docs/Deployment.md`
  - 适合低配置与快速演示；数据多存于配置文件
- 全模块安装（含管理端/数据库/OTA/声纹等）

  - 参考：`docs/Deployment_all.md`
  - 适合完整功能体验；管理能力与数据持久化完善
- Docker 与 Nginx

  - 顶层 `Dockerfile-*`、`docs/docker/*`（如 `nginx.conf`、`start.sh`）

---

### 六、常见“我想要…”到操作路径

- 我想测一测链路是否通：

  - 打开 `main/xiaozhi-server/test/test_page.html`，用 Chrome 测音频收发
  - 运行 `python main/xiaozhi-server/performance_tester.py` 测速
- 我想切换为“流式低延迟配置”：

  - 按 `README.md` 的“配置说明和推荐”表格，修改 `main/xiaozhi-server/config.yaml` 对应模型与密钥
- 我想用 MCP 工具控制设备：

  - 阅读 `docs/mcp-endpoint-integration.md`、`docs/mqtt-gateway-integration.md`
  - Python 端实现/启用工具：`plugins_func/` 与 `core/mcp/`
  - 管理端下发：`manager-api` + `manager-web`
- 我想启用视觉识别/拍照识物：

  - 参考 `docs/mcp-vision-integration.md`，在 `config.yaml` 配置 VLLM
- 我想本地跑 TTS（如 Index/TTS、PaddleSpeech、FishSpeech）：

  - 参考 `docs/index-stream-integration.md`、`docs/paddlespeech-deploy.md`、`docs/fish-speech-integration.md`

---

### 七、与文档的交叉索引（精选）

- 部署：`docs/Deployment.md`、`docs/Deployment_all.md`、`docs/docker-build.md`、`docs/dev-ops-integration.md`
- MQTT 网关：`docs/mqtt-gateway-integration.md`
- MCP：`docs/mcp-endpoint-enable.md`、`docs/mcp-endpoint-integration.md`、`docs/mcp-get-device-info.md`
- 视觉：`docs/mcp-vision-integration.md`
- 语音与合成：`docs/index-stream-integration.md`、`docs/paddlespeech-deploy.md`、`docs/fish-speech-integration.md`
- 声纹：`docs/voiceprint-integration.md`
- 常见问题：`docs/FAQ.md`

---

### 八、关键约定与排错提示

- OpenAI 接口兼容：多数 LLM/VLLM 通过统一的 OpenAI 兼容协议接入，便于切换与 A/B 测试。
- 模型只测已配置密钥：性能测试工具仅会对已配置的模型进行测试（见 `README.md` 提示）。
- 安全与生产：`README.md` 明确警示未通过网安测评，不建议生产使用；公网部署务必加固。

---

### 九、你可能会修改的文件（按频率）

1) `main/xiaozhi-server/config.yaml`：模型、密钥、端口、开关项
2) `main/xiaozhi-server/app.py`：服务启动与路由初始化（若新增端点）
3) `main/xiaozhi-server/core/*`：接入新模型/新工具/新流程编排
4) `main/xiaozhi-server/plugins_func/*`：新增插件化工具函数
5) `main/manager-api/*` 与 `main/manager-web/*`：需要在智控台侧新增页面/接口/功能

---

### 十、快速校验（连通性）

- WebSocket：使用 `README.md` 中提供的测试地址或本地端口，验证 `wss://.../xiaozhi/v1/` 是否能建连并收发
- OTA/HTTP：访问 `.../xiaozhi/ota/` 检查版本/连通
- 智控台：`manager-web` 本地运行或访问演示地址，登录并下发指令到设备

---

---

### 十一、核心数据流与处理流程详解

#### 11.1 服务启动流程

**入口：`app.py`**
```python
# 1. 加载配置（支持本地配置和API配置）
config = load_config()

# 2. 初始化认证密钥（优先级：config.yaml > manager-api.secret > 自动生成）
auth_key = config["server"].get("auth_key", "")

# 3. 启动 WebSocket 服务器（端口默认8000）
ws_server = WebSocketServer(config)

# 4. 启动 HTTP 服务器（端口默认8003，提供OTA、视觉分析接口）
ota_server = SimpleHttpServer(config)
```

**WebSocket 服务器初始化：`core/websocket_server.py`**
- 在 `__init__` 中调用 `initialize_modules()` 初始化全局模块（VAD、ASR、LLM、Memory、Intent）
- 这些模块在服务器级别共享，但每个连接会创建独立的 `ConnectionHandler` 实例

#### 11.2 连接建立与认证流程

**连接处理：`core/websocket_server.py::_handle_connection()`**
1. 从 HTTP Headers 或 URL 查询参数获取 `device-id`、`client-id`、`authorization`
2. 执行认证（如果启用）：`_handle_auth()` 验证 JWT Token
3. 创建 `ConnectionHandler` 实例（每个设备连接一个）
4. 调用 `handler.handle_connection(websocket)` 处理连接生命周期

**连接初始化：`core/connection.py::handle_connection()`**
1. 解析 Headers，获取设备ID、客户端IP
2. 检查是否来自 MQTT 网关（通过 URL 参数 `?from=mqtt_gateway`）
3. 启动超时检查任务（长时间无语音自动关闭）
4. 获取差异化配置（如果 `read_config_from_api=True`，从 Java API 获取设备专属配置）
5. 异步初始化各模块（TTS、工具处理器等）
6. 发送欢迎消息（包含 session_id）
7. 进入消息循环：`_handle_messages()`

#### 11.3 音频消息处理流程（核心对话链路）

**接收音频：`core/handle/receiveAudioHandle.py::handleAudioMessage()`**
```
设备发送 Opus 音频包
    ↓
VAD 检测（SileroVAD）：判断是否有语音
    ↓
如果有语音：
  - 检查是否刚唤醒（just_woken_up），短暂忽略VAD
  - 如果客户端正在说话且非manual模式，执行打断处理
  - 更新 last_activity_time（用于超时检测）
    ↓
调用 ASR.receive_audio()：
  - 将音频加入队列（asr_audio_queue）
  - ASR 在后台线程处理音频，识别完成后调用回调
    ↓
ASR 识别完成 → startToChat(conn, text)
```

**开始对话：`core/handle/receiveAudioHandle.py::startToChat()`**
```
1. 解析说话人信息（如果ASR返回JSON格式，包含speaker字段）
2. 检查设备绑定状态（need_bind）
3. 检查输出字数限制（max_output_size）
4. 处理打断（如果客户端正在说话）
5. 意图识别：handle_user_intent()
   - 检查退出命令
   - 检查唤醒词
   - 如果 intent_type == "function_call"，跳过意图分析，直接进入聊天
   - 否则使用 LLM 进行意图分析
6. 如果意图未被处理，继续常规聊天：
   - 发送 STT 消息（通知客户端开始识别）
   - 提交聊天任务到线程池：conn.executor.submit(conn.chat, text)
```

**聊天处理：`core/connection.py::chat()`**
```
1. 生成 sentence_id（用于标识本次对话）
2. 将用户消息加入对话历史（dialogue.put()）
3. 发送 TTS 开始消息（FIRST 类型）
4. 准备工具函数列表（如果使用 function_call）
5. 调用 LLM：
   - 构建消息历史（包含系统提示词、记忆总结、对话历史）
   - 如果使用 function_call，传入工具函数描述
   - LLM 返回响应（可能包含工具调用）
6. 处理 LLM 响应：
   - 如果是工具调用，执行工具并递归调用 chat()（depth+1）
   - 如果是普通文本，加入对话历史，发送到 TTS 队列
7. 更新记忆（Memory）
```

**TTS 处理与音频发送：`core/handle/sendAudioHandle.py`**
```
TTS 模块从队列获取文本（tts_text_queue）
    ↓
调用 TTS 提供者（流式/非流式）
    ↓
TTS 返回音频数据（Opus 格式）
    ↓
加入 TTS 音频队列（tts_audio_queue）
    ↓
sendAudioMessage() 处理：
  - 发送 sentence_start 消息
  - 调用 sendAudio() 发送音频包
    ↓
sendAudio() 流控逻辑：
  - 前5个包快速发送（预缓冲）
  - 后续包按帧时长（60ms）计算延迟
  - 如果来自 MQTT 网关，添加16字节头部（包含时间戳、序列号）
  - 发送到 WebSocket
    ↓
发送完成后：
  - 如果是最后一句（LAST），发送 stop 消息
  - 如果 close_after_chat=True，关闭连接
```

#### 11.4 文本消息处理流程

**消息路由：`core/handle/textMessageProcessor.py`**
- 解析 JSON 消息，获取 `type` 字段
- 从注册表获取对应的处理器：`TextMessageHandlerRegistry`
- 支持的文本消息类型：
  - `hello`：设备连接握手（`HelloMessageHandler`）
  - `listen`：监听状态变化（`ListenMessageHandler`）
  - `iot`：IOT 指令（`IotMessageHandler`）
  - `mcp`：MCP 协议消息（`McpMessageHandler`）
  - `server`：服务端动作（`ServerMessageHandler`）
  - `abort`：打断消息（`AbortMessageHandler`）

#### 11.5 工具调用系统

**统一工具管理器：`core/providers/tools/unified_tool_manager.py`**
- `ToolManager` 管理所有类型的工具执行器
- 工具类型（`ToolType`）：
  - `DEVICE_IOT`：设备 IOT 协议工具
  - `DEVICE_MCP`：设备 MCP 协议工具
  - `SERVER_MCP`：服务端 MCP 协议工具
  - `MCP_ENDPOINT`：MCP 接入点工具
  - `SERVER_PLUGINS`：服务端插件工具

**工具调用流程：**
```
LLM 返回工具调用请求
    ↓
UnifiedToolHandler.get_functions() 获取所有工具描述（OpenAI格式）
    ↓
LLM 选择工具并传入参数
    ↓
UnifiedToolHandler.execute_tool()：
  - 查找工具类型
  - 获取对应的执行器（Executor）
  - 执行工具调用
    ↓
工具执行结果返回给 LLM
    ↓
LLM 生成最终回复
```

**插件系统：`plugins_func/`**
- `loadplugins.py`：自动导入 `functions/` 目录下的所有插件模块
- `register.py`：`Action` 装饰器注册插件函数
- 插件函数返回 `ActionResponse`，包含 `action`（动作类型）和 `response`（响应内容）

#### 11.6 配置加载机制

**配置加载：`config/config_loader.py`**
1. **本地配置加载**：
   - 默认配置：`config.yaml`
   - 自定义配置：`data/.config.yaml`（优先级更高，递归合并）
2. **API 配置加载**（如果 `read_config_from_api=True`）：
   - 调用 `get_config_from_api()` 从 Java API 获取配置
   - 合并本地 server 配置（IP、端口等）
3. **缓存机制**：
   - 使用 `CacheManager` 缓存配置，避免重复加载
4. **私有配置**（每个设备）：
   - 连接建立时调用 `get_private_config_from_api()` 获取设备专属配置
   - 包括：模型选择、提示词、功能开关等

**配置更新：`core/websocket_server.py::update_config()`**
- 支持热更新配置（通过 API 触发）
- 检查 VAD/ASR 类型是否变化，决定是否重新初始化
- 更新全局模块实例

#### 11.7 模块初始化流程

**模块初始化：`core/utils/modules_initialize.py`**
```python
initialize_modules(logger, config, init_vad, init_asr, init_llm, init_tts, init_memory, init_intent)
```
- 根据 `selected_module` 配置选择对应的提供者
- 调用各模块的 `create_instance()` 创建实例
- 返回模块字典：`{"vad": ..., "asr": ..., "llm": ..., ...}`

**TTS/ASR 初始化**：
- 支持动态初始化（每个连接独立）
- 从配置读取提供者类型和参数
- 创建对应的提供者实例

#### 11.8 记忆系统

**记忆处理：`core/providers/memory/`**
- **mem_local_short**：本地短期记忆
  - 维护对话历史窗口
  - 定期总结并压缩历史
- **mem0ai**：外部记忆服务
  - 通过 API 调用 mem0ai 服务
  - 支持记忆存储和检索

**记忆使用流程：**
```
对话开始时：
  - 从 Memory 获取历史总结
  - 构建系统提示词（包含记忆上下文）
    ↓
对话进行中：
  - 将用户消息和AI回复加入对话历史
    ↓
对话结束时：
  - 调用 Memory.update() 更新记忆
  - 如果是本地记忆，可能触发总结
```

#### 11.9 声纹识别

**声纹处理：`core/utils/voiceprint_provider.py`**
- 与 ASR 并行处理（不阻塞语音识别）
- ASR 返回识别文本时，同时返回说话人信息
- 说话人信息传递给 LLM，用于个性化回应

#### 11.10 超时与连接管理

**超时检测：`core/connection.py::_check_timeout()`**
- 定期检查 `last_activity_time`
- 如果超过 `close_connection_no_voice_time`（默认120秒），触发结束对话
- 发送结束提示语（如果启用），然后关闭连接

**连接关闭：**
- 正常关闭：发送完所有音频后关闭
- 异常关闭：连接断开、认证失败等
- 主动关闭：客户端发送关闭消息、超时等

---

### 十二、关键数据结构

#### 12.1 ConnectionHandler 核心属性

```python
# 连接信息
self.websocket          # WebSocket 连接对象
self.device_id          # 设备ID
self.session_id         # 会话ID（UUID）
self.headers            # HTTP Headers

# 状态管理
self.client_abort       # 客户端打断标志
self.client_is_speaking # 客户端是否正在说话
self.client_listen_mode # 监听模式（auto/manual）

# 模块实例
self.vad                # VAD 实例
self.asr                # ASR 实例
self.tts                # TTS 实例（每个连接独立）
self.llm                # LLM 实例（共享）
self.memory             # Memory 实例（共享）
self.intent             # Intent 实例（共享）

# 对话管理
self.dialogue           # Dialogue 对象（对话历史）
self.prompt             # 系统提示词
self.sentence_id        # 当前句子ID

# 工具调用
self.func_handler       # UnifiedToolHandler 实例

# 音频队列
self.asr_audio_queue    # ASR 音频队列
self.tts.tts_text_queue # TTS 文本队列
self.tts.tts_audio_queue # TTS 音频队列
```

#### 12.2 消息格式

**WebSocket 消息类型：**
- **二进制消息**：Opus 音频包
- **文本消息（JSON）**：
  ```json
  {
    "type": "hello|listen|iot|mcp|server|abort",
    "state": "start|stop|detect",
    "text": "...",
    ...
  }
  ```

**TTS 消息DTO：`core/providers/tts/dto/dto.py`**
```python
TTSMessageDTO(
    sentence_id: str,        # 句子ID
    sentence_type: SentenceType,  # FIRST|MIDDLE|LAST
    content_type: ContentType,    # TEXT|ACTION
    content: str,            # 文本内容
)
```

#### 12.3 配置结构

**主要配置项（`config.yaml`）：**
```yaml
server:
  ip: "0.0.0.0"
  port: 8000
  http_port: 8003
  auth_key: "..."
  auth:
    enabled: false
    allowed_devices: []

selected_module:
  VAD: "SileroVAD"
  ASR: "FunASRLocal"
  LLM: "ChatGLMLLM"
  TTS: "LinkeraiTTS"
  Memory: "mem_local_short"
  Intent: "function_call"

# 各模块配置
VAD: {...}
ASR: {...}
LLM: {...}
TTS: {...}
Memory: {...}
Intent: {...}
```

---

### 十三、扩展点与自定义

#### 13.1 添加新的 ASR 提供者

1. 在 `core/providers/asr/` 创建新文件（如 `my_asr.py`）
2. 继承 `ASRBase` 基类
3. 实现 `receive_audio()` 方法
4. 在 `core/utils/asr.py` 的 `create_instance()` 中添加创建逻辑
5. 在 `config.yaml` 中添加配置项

#### 13.2 添加新的 TTS 提供者

1. 在 `core/providers/tts/` 创建新文件
2. 继承 `TTSBase` 基类
3. 实现流式/非流式接口
4. 在 `core/utils/tts.py` 的 `create_instance()` 中添加创建逻辑

#### 13.3 添加新的插件函数

1. 在 `plugins_func/functions/` 创建新文件（如 `my_function.py`）
2. 使用 `@Action` 装饰器注册函数
3. 函数返回 `ActionResponse`
4. 系统会自动加载（通过 `loadplugins.py`）

#### 13.4 添加新的工具类型

1. 在 `core/providers/tools/base/tool_types.py` 添加新的 `ToolType`
2. 创建对应的执行器目录（如 `my_tool/`）
3. 实现 `ToolExecutor` 接口
4. 在 `UnifiedToolHandler` 中注册执行器

---

如需进一步细化到具体类/函数级别，请告知你关注的能力（如“流式 ASR 具体链路”或“某云厂商 TTS 适配”），我将补充到本文并给出代码行级索引。
