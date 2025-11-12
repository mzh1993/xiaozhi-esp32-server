## 本地部署 GPT-SoVITS v4 实施方案

### 1. 背景与目标

- **目标**：在本地 GPU 服务器 `/home/neousys/mzh/xiaozhi` 上部署开源项目 [GPT-SoVITS](https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e) v4 版本，并将其作为 `xiaozhi-esp32-server` 的 TTS 后端，实现自定义音色的低延迟语音合成。
- **范围**：
  1. 复用既有目录 `/home/neousys/mzh/xiaozhi/TTS/GPT-SoVITS`，完成环境准备、模型下载、推理服务部署。
  2. 在 `xiaozhi-esp32-server` 中新增或扩展
  3.  `gpt_sovits` TTS Provider 以支持 v4 API。
  4. 整合至当前部署流程（参考 `docs/0-服务器启动文档.md`、`docs/0-project-architecture-overview.md` 中的 TTS 模块说明）。

### 2. 依赖与环境要求

| 组件            | 要求/说明                                                                                               |
| --------------- | ------------------------------------------------------------------------------------------------------- |
| 操作系统        | Ubuntu 20.04+（当前为 Linux 5.15.0-67-generic，可满足）                                                 |
| GPU             | 建议 ≥ 12GB 显存（根据 GPT-SoVITS v4 推理建议）                                                        |
| GPU 驱动 & CUDA | 驱动 ≥ 525，CUDA ≥ 11.6；需与 PyTorch 版本兼容                                                        |
| Python          | 3.10（可在 Conda 环境中创建，建议与 `xiaozhi-server` 分离）                                           |
| Conda/Miniconda | 使用 `conda create -n gpt-sovits python=3.10`                                                         |
| 依赖库          | PyTorch、torchvision、torchaudio、fairseq、gradio、ffmpeg、pydantic 等（详见项目 `requirements.txt`） |
| 端口占用        | GPT-SoVITS 默认提供 HTTP/Gradio 服务，建议占用 `9880`（与 `config.yaml` 中现有示例保持一致）        |
| 数据/模型       | 需要下载 v4 模型权重（`SoVITS_weights.pth`、`GPT_weights.pth` 等）及参考音频/文本素材               |

### 3. 目录与资源规划

```
/home/neousys/mzh/xiaozhi/
├── TTS/
│   └── GPT-SoVITS/           # v4 项目代码与模型目录
├── xiaozhi-esp32-server/
│   ├── main/xiaozhi-server/  # Python 核心服务
│   └── docs/                 # 文档
```

- 建议在 `GPT-SoVITS` 仓库内创建 `checkpoints/v4/` 用于存放下载或训练出的 v4 权重。
- 若需自定义音色，准备不少于 10 分钟的高质量参考音频，存放于 `dataset/`。

### 4. 部署流程

#### 4.1 获取与更新代码

```bash
cd /home/neousys/mzh/xiaozhi/TTS/GPT-SoVITS
git pull origin main            # 或者切换到 v4 对应分支/tag
```

> 如需保持 v4 版本，可创建本地分支 `git checkout -b gpt-sovits-v4` 并锁定依赖。

#### 4.2 创建并激活 Conda 环境

```bash
conda create -n gpt-sovits python=3.10 -y
conda activate gpt-sovits
```

#### 4.3 安装依赖

```bash
cd /home/neousys/mzh/xiaozhi/TTS/GPT-SoVITS
pip install -r requirements.txt

# 根据 GPU 情况安装匹配版本的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 其他可能依赖
pip install gradio onnxruntime soundfile pydantic==1.10.9
sudo apt-get install ffmpeg -y
```

> 若 v4 版本有额外依赖（例如最新版的 `fairseq` 或 `flash-attn`），请参考项目 README 逐项安装。

#### 4.4 下载或准备模型权重

1. 访问官方发布页（或提供的网盘链接）下载 v4 权重，例如：
   - `G_XXX.pth`（SoVITS 声码器）
   - `D_XXX.pth`（鉴别器，可选）
   - `GPT_weights.pth`
   - `cnhubert_base.pt`、`s3prl_base` 等前端模型
2. 将权重放入 `checkpoints/v4/` 并在项目配置文件中更新路径：

```bash
mkdir -p checkpoints/v4
# 假设已经下载并放入该目录
```

3. 如需自建音色，请按照官方文档完成数据集整理、标注和训练。训练完成后，将生成的权重同样放入 `checkpoints/v4/`。

#### 4.5 配置推理服务

- 编辑 `configs/inference_v4.yaml`（若不存在可复制 v3 模板）：

```yaml
server:
  host: 0.0.0.0
  port: 9880

model:
  sovits_path: checkpoints/v4/G_latest.pth
  gpt_path: checkpoints/v4/GPT_latest.pth
  hubert_path: checkpoints/v4/chinese-hubert-base.pt

inference:
  speaker: default_speaker
  text_lang: zh
  ref_wav_path: assets/ref/default.wav
  ref_text: "你好，欢迎体验小智语音。"
  device: "cuda:0"
```

- 根据需要开启 HTTP/REST 接口（若 v4 默认仅提供 Gradio，可在仓库的 `inference.py` 或 `app.py` 中启用 FastAPI/Flask 模块）。

#### 4.6 启动推理服务

```bash
conda activate gpt-sovits
cd /home/neousys/mzh/xiaozhi/TTS/GPT-SoVITS
python app.py --config configs/inference_v4.yaml
```

> 若官方提供 `uvicorn`/`gunicorn` 启动方式，请按其文档执行，例如：
>
> ```bash
> uvicorn inference_server:app --host 0.0.0.0 --port 9880
> ```
>
> 启动后通过浏览器访问 `http://<server-ip>:9880` 验证是否能进行语音合成。

#### 4.7 进程守护（可选）

- 如果需后台运行，可使用 `tmux`, `screen` 或编写 `systemd` unit：

```bash
# 示例 systemd 服务文件（/etc/systemd/system/gpt-sovits.service）
[Unit]
Description=GPT-SoVITS v4 Service
After=network.target

[Service]
Type=simple
User=neousys
WorkingDirectory=/home/neousys/mzh/xiaozhi/TTS/GPT-SoVITS
ExecStart=/home/neousys/anaconda3/envs/gpt-sovits/bin/python app.py --config configs/inference_v4.yaml
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 5. 与 `xiaozhi-esp32-server` 的集成方案

#### 5.1 Provider 适配

1. 参考 `main/xiaozhi-server/core/providers/tts/gpt_sovits_v3.py`，在同级目录新增 `gpt_sovits_v4.py`。初步适配方式：
   - 若 v4 服务提供 REST 接口，构造请求参数（文本、语言、参考音频等）并 `POST/GET` 至 `http://127.0.0.1:9880/tts`。
   - 若响应返回音频二进制（WAV/PCM），保持与现有 Provider 一致的写文件/返回内容逻辑。
   - 根据 v4 API 的字段命名（例如 `style`, `emotion`, `seed` 等）补充配置项。
2. 在 `core/utils/tts.py::create_instance()` 中增加 `elif provider_type == "gpt_sovits_v4":` 分支，返回新 Provider。
3. 在 `config.yaml` 的 `TTS` 配置节点追加默认模板：

```yaml
  GPT_SOVITS_V4:
    type: gpt_sovits_v4
    url: "http://127.0.0.1:9880"
    output_dir: tmp/
    text_language: "zh"
    refer_wav_path: "assets/ref/default.wav"
    prompt_language: "zh"
    prompt_text: ""
    speed: 1.0
    emotion: "default"
```

4. 若需要在管理后台配置中出现 v4 选项，可参考 `main/manager-api/src/main/resources/db/changelog/202504112044.sql` 新增一条 `ai_model_config` 记录。

#### 5.2 本地配置

- 在 `main/xiaozhi-server/data/.config.yaml` 中启用：

```yaml
selected_module:
  TTS: GPT_SOVITS_V4

TTS:
  GPT_SOVITS_V4:
    type: gpt_sovits_v4
    url: http://127.0.0.1:9880
    output_dir: tmp/
    text_language: zh
    refer_wav_path: /home/neousys/mzh/xiaozhi/TTS/GPT-SoVITS/assets/ref/default.wav
    prompt_language: zh
    prompt_text: ""
    speed: 1.0
```

#### 5.3 验证流程

1. 启动 GPT-SoVITS v4 服务（确保 9880 端口监听）。
2. 重启 `xiaozhi-server`：

```bash
pkill -f "xiaozhi-server/app.py"
cd /home/neousys/mzh/xiaozhi/xiaozhi-esp32-server/main/xiaozhi-server
/home/neousys/anaconda3/envs/xiaozhi-esp32-server/bin/python app.py > /tmp/xiaozhi-server.log 2>&1 &
```

3. 打开 `main/xiaozhi-server/test/test_page.html`，将 OTA 地址指向 `http://127.0.0.1:8003/xiaozhi/ota/`，发送测试文本，观察是否由 GPT-SoVITS 合成语音。
4. 如需脚本验证，可直接调用 REST 接口：

```bash
curl -G "http://127.0.0.1:9880/tts" \
  --data-urlencode "text=你好，欢迎体验GPT-SoVITS v4" \
  --data-urlencode "text_language=zh" \
  --data-urlencode "refer_wav_path=assets/ref/default.wav" \
  --output /tmp/gpt_sovits_test.wav
```

### 6. 运维与监控

- **日志**：GPT-SoVITS 服务若采用 `uvicorn`，默认输出在控制台，可重定向到 `/var/log/gpt-sovits.log`。
- **资源监控**：使用 `nvidia-smi -l 5`、`htop` 监控 GPU/CPU 占用。
- **进程管理**：配合 `systemd` 实现开机自启与自动拉起。
- **备份**：定期备份 `checkpoints/v4/`、自定义音色参考音频，以及配置文件。

### 7. 风险与应对

| 风险点                  | 影响                        | 应对措施                                                                      |
| ----------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| PyTorch/CUDA 版本不匹配 | 模型无法加载或运行缓慢      | 安装与 GPU 匹配的 PyTorch 版本，使用官方镜像源                                |
| v4 API 变更或不兼容     | Provider 解析失败、调用异常 | 在适配前阅读 v4 API 文档，必要时提交 Issue 或参考源码确认字段                 |
| 端口冲突（9880）        | 服务启动失败                | 修改 `inference_v4.yaml` 中的端口或释放占用                                 |
| 显存不足                | 推理失败、延迟过高          | 降低 `sample_steps`、`speed`、`parallel_infer` 等配置或更换更大显存 GPU |
| 素材/权重丢失           | 无法恢复自定义音色          | 将权重和音频备份至 NAS 或对象存储                                             |

### 8. 时间规划（建议）

| 阶段                    | 说明                                      | 预估时间 |
| ----------------------- | ----------------------------------------- | -------- |
| 环境准备                | Conda、依赖安装、下载权重                 | 0.5 天   |
| 服务部署与启动          | 配置 YAML、启动推理服务                   | 0.5 天   |
| Provider 适配与代码更新 | 新增 `gpt_sovits_v4` Provider、配置模板 | 0.5 天   |
| 联调与测试              | 通过测试页、脚本验证全链路                | 0.5 天   |
| 文档与运维脚本完善      | 更新项目文档、systemd、备份策略           | 0.5 天   |

> 整体 2~3 天可完成初版部署与联调，后续可根据音色训练需求投入更多时间。

### 9. 后续工作

1. **功能完善**：根据使用情况优化 Provider（如支持流式响应、返回分片音频）。
2. **管理端集成**：在管理后台增加参数配置表单，使非技术人员可切换/管理 TTS 模型。
3. **模型版本管理**：记录 v4 权重来源及更新日志，必要时保留 v3 作为回退选项。
4. **自动化**：将部署脚本纳入项目 CI/CD（可参考 `docs/docker-build.md`）。

---

通过上述方案，可在本地 GPU 环境部署 GPT-SoVITS v4，并顺利接入 `xiaozhi-esp32-server`，满足低延迟、可控音色的语音合成需求。后续如需进一步扩展（例如云端部署、Docker 镜像化），可在此基础上延伸。
