# Elysia Tunnel GUI · 本地大模型分享

简体中文 | [English](README.en.md)

[![发行版](https://img.shields.io/github/v/release/FuFu-Flash/elysia-tunnel-gui?style=flat-square&color=C24C86)](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases/latest)
[![Windows 10/11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4?style=flat-square)](#下载与使用)
[![架构 x64](https://img.shields.io/badge/architecture-x64-6A4C93?style=flat-square)](PACKAGING.md)

**自动识别本地大模型 API，一键分享给远程客户端。**

让本地大模型，也能被远程调用。例如，在 [Strata](https://github.com/Niko1221/Strata) 中运行本地模型，用本工具自动识别并分享 API，再在 [DeepSeek Harness（DSH）](https://github.com/deepseek-ai/deepseek-harness) 中连接它。模型仍在你的电脑上运行，远程客户端通过分享地址发送请求。

这是一个 Windows 图形工具，支持 Cloudflare / FRP、多条隧道和托盘后台运行。也可以填写本地端口，把网站或其他 HTTP 服务分享给朋友。

**[下载 ElysiaTunnel.exe](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases/latest/download/ElysiaTunnel.exe)** · [Strata + DSH 图文教程](#strata-dsh-tutorial) · [查看最新版本](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases/latest)

![本地模型自动识别与分享](docs/model-sharing.png)

## 下载与使用

下载 `ElysiaTunnel.exe` 后双击运行。适用于 Windows 10 / 11 x64，已包含 Python、Qt、Cloudflare 和 FRP 穿透内核，无需另行安装依赖。单文件启动时会解压运行资源，首次打开需要稍等片刻；建立隧道需要联网。

v0.4.0 的 EXE 约 75.33 MiB。下载页同时提供 `.sha256` 文件，可用于核对下载完整性。

<a id="strata-dsh-tutorial"></a>

## 图文教程：Strata → DeepSeek Harness

这份教程用 Strata 作为模型服务端，用 DeepSeek Harness 作为远程客户端。在运行模型的电脑上完成第 1–3 步，在使用 DSH 的电脑上完成第 4 步。

教程截图来自实际软件界面，使用演示数据：`local-model` 是占位模型名，`https://your-tunnel.example/v1` 是示例地址，不能直接使用。请以你自己的识别结果和分享地址为准。DSH 配图采用 0.2.0-rc.2，后续版本的菜单可能变化。

**先选择合适的穿透方式。** 当前 DSH 版本没有关闭流式输出的开关，本文的 DSH 连接步骤使用已配置的 FRP 或 Cloudflare 固定域名。Cloudflare 官方明确说明 [Quick Tunnel 不支持 SSE](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/#limitations)；临时地址适合使用「复制调用示例」中的 Python 非流式请求，不作为 DSH 流式连接方案。FRP 和固定域名的公网模型分享尚未实测。

### 1. 在 Strata 中启动本地模型

按照 [Strata 官方安装说明](https://github.com/Niko1221/Strata#install)准备服务。Windows 中双击 `START-HERE.bat`，等待模型加载完成，再打开 `http://127.0.0.1:8080`，点击「关于」查看接口地址与模型名称。如果你改过端口，后续使用自己的端口；Strata 的安装、模型下载与硬件要求由它的项目说明负责。

公开分享前，在 Strata 当前模型的 `strata-<model>.json` 配置中设置非空的 `api_key`，重启服务使它生效。保留 `127.0.0.1` 监听即可，本工具会转发本机服务；配置位置见 [Strata 官方说明](https://github.com/Niko1221/Strata/blob/main/docs/INSTALL.md#where-things-are-stored)。网页中的「API 密钥」输入框用于浏览器连接服务，不能替代服务端 `api_key` 的配置。

![Strata 关于页面：确认本机 API 地址](docs/tutorial/strata-about.png)

*Strata 界面演示。实际使用时，先确认自己的模型服务已就绪；图中的模型与运行数据是占位内容。*

### 2. 自动识别模型 API，并开始分享

打开本工具的「模型分享」页面，程序会自动查找本机模型 API。设置了 Key 的服务可能先显示为待验证：填入 Strata 的端口（默认 `8080`）和已有的 API Key，点击「识别端口」。读取到模型列表后，选择服务与模型。

![自动识别 Strata 的模型 API](docs/tutorial/elysia-detect.png)

*识别完成后的界面演示。模型名称以程序实际读到的列表为准。检测只读取模型列表，不加载模型、不发起推理，检测用 Key 不会保存。*

选择分享方式，再点击「开始分享」。使用 Cloudflare 固定域名时，在「设置」的「外网地址，由你选择」中选择「固定域名」，完成授权和域名绑定；需要 Cloudflare 托管的自有域名。使用 FRP 时，先配置自己的 FRPS 服务器，填写远程映射端口。

### 3. 复制客户端连接信息

连接成功后，在「客户端连接」中点击「复制 Base URL」和「复制模型 ID」。Base URL 应包含末尾的 `/v1`，例如 `https://your-tunnel.example/v1`；模型名称直接复制，不要照抄截图中的 `local-model`。

![复制模型 API 地址与模型 ID](docs/tutorial/elysia-share.png)

*连接信息演示。图中的域名和连接状态均为示例；实际连接成功后，使用你自己的地址。远程客户端不能使用服务端电脑的 `127.0.0.1:8080`。*

### 4. 在 DeepSeek Harness 中连接模型

安装并打开 [DeepSeek Harness](https://www.deepseek.com/en/download/)。在左下角进入「更多 → 设置 → 模型」，点击「添加模型提供商」，选择「自定义模型 API」。按下面填写：

| 字段 | 填写内容 |
| --- | --- |
| Provider ID | 例如 `strata-remote`；以小写字母开头，仅使用小写字母、数字和短横线 |
| 显示名称 | 例如 `Strata` |
| API 协议 | `OpenAI Chat Completions` |
| API 地址 | 上一步复制的 Base URL，保留末尾 `/v1` |
| API 密钥 | Strata 中设置的 API Key |
| 模型目录 / Model ID | 上一步复制的模型 ID，或获取可用模型后选择 |

![DeepSeek Harness 自定义模型提供商配置](docs/tutorial/dsh-provider.png)

*DSH 配置演示。示例地址不能使用，密钥请填写你自己的 Strata API Key。不要选择 OpenAI Responses 或 Anthropic 协议来代替本教程中的 Chat Completions。*

点击「获取可用模型」，勾选要用的模型并点击「添加所选」。如果无法获取列表，点击「添加模型」，手动填写第 3 步复制的模型 ID。最后点击「创建提供商」。

回到聊天页，点击输入框底部的当前模型名称，进入「模型」列表，选择刚添加的 Strata 模型。

![DeepSeek Harness 在模型下拉列表中选择 Strata 模型](docs/tutorial/dsh-model.png)

发送一句简短消息，例如「只回复 OK，不调用工具」，确认连接。使用期间保持 Strata 与分享隧道运行。

![DeepSeek Harness 选择模型并发送消息](docs/tutorial/dsh-chat.png)

*DSH 聊天操作演示，回复来自本地测试服务，不是新增的公网 Strata 实测。此前真实 DSH 连接 Strata 的一次公网短回复结果见下方「测试情况」。*

停止分享或退出本工具后，远程客户端就无法继续通过这条隧道调用模型。临时地址重连后会变化，固定域名则以你配置的域名为准。

选择模型用于生成调用示例；分享的是整个服务端口，其他模型和 HTTP 路径也可能被访问。检测 Key 不会替模型服务添加鉴权。使用 Ollama 等其他服务时也一样，请先配置访问控制；[Ollama 本地 API 无需鉴权](https://docs.ollama.com/api/authentication)。

## 分享本地网站

想把本地跑着的小网站发给朋友看看，却又不想临时翻一堆命令？填个端口，点一下「开始穿透」，等外网地址出现，再复制给对方。

1. 先启动本地网站或应用，确认能够在这台电脑上访问。
2. 打开「服务穿透」，选择服务类型并填写本地端口。例如本地地址为 `http://localhost:8080`，就选 HTTP、填 `8080`。
3. 点击「开始穿透」，连接成功后复制外网地址。选择 Cloudflare 临时地址时，无需登录或准备域名。

停止隧道后，对应的外网地址就不能继续访问本地服务；重新连接时，临时地址会变化。

![服务穿透主界面](docs/screenshot.png)

## 日常使用

- **同时管理多条隧道**：分别命名、配置端口、查看地址和日志，单独或全部启动、停止。
- **托盘后台运行**：点击窗口关闭按钮会隐藏到托盘；选择「退出」才会停止全部隧道并退出程序。
- **保存常用 FRPS**：集中管理多台 FRPS 服务器，每条隧道可选择自己的配置；Cloudflare 隧道共用一个账户。
- **本机端口检测与实时日志**：查找正在监听的端口，复制外网地址，停止或重启连接。
- **爱莉粉、主题与点击波纹**：在设置中调整主题颜色和动画速度，也可以关闭动画。窗口采用无标题文字的顶部控制区，支持拖动、调整大小、最大化和还原。
- **简体中文 / English**：界面语言即时切换并记住选择，穿透内核的原始日志保留原文。
- **适应窗口大小**：宽窗口并排显示配置与状态，窄窗口改为一列，可滚动访问内容；设置页平滑切换。

![设置页面](docs/settings.png)

## 穿透方式

| 方式 | 用途 | 需要准备 |
| --- | --- | --- |
| Cloudflare 临时地址 | 临时分享 HTTP / HTTPS 服务；模型 API 用于非流式请求 | 已运行的本地服务和网络连接 |
| Cloudflare 固定域名 | 为服务使用自己的固定域名 | Cloudflare 托管的域名、账户授权及隧道绑定 |
| FRP | 通过自己的服务器进行 TCP 端口映射 | FRPS 服务器配置及可访问的远程映射端口 |
| 自动模式 | HTTP / HTTPS 优先 Cloudflare，配置 FRP 后可作后备 | 对应方式所需配置 |

固定域名不会自动换成临时地址。Cloudflare 真实账户授权、创建命名隧道、DNS 绑定和固定域名连通性尚未实测，见 [固定域名说明](docs/cloudflare-fixed-domain.md)。真实 FRPS 转发也尚未实测；模型分享中的 FRP 当前使用 HTTP，公网访问不加密。

隧道配置保存在本机，下次打开可继续使用，但不会自动启动连接。保存的 FRPS token 使用 Windows 用户级加密。

## 测试情况

本机 Windows 11 检查覆盖中英文切换、设置页往返、多隧道进程管理、FRPS 配置切换、托盘与退出清理，以及点击波纹、键盘操作、动画速度和关闭动画。窗口检查覆盖调整大小时位置不漂移、最大化使用屏幕工作区、还原后保留位置和尺寸。

本地模型识别与分享检查覆盖模型列表读取、检测 Key 的使用范围、客户端地址与示例复制、已有隧道配置保护、HTTP 转发及停止清理。本轮通过 Cloudflare 临时地址完成 Strata 服务的公网模型列表读取和一次非流式请求；另在真实 DeepSeek Harness（DSH）Windows 客户端中获取模型并完成一次简短回复。

DSH 的一次请求成功不代表 Quick Tunnel 支持通用 SSE 流式输出，也不代表所有模型、客户端或长期运行已经验证。Windows 10、真实 FRPS 转发、Cloudflare 账户与固定域名操作、HTTPS 源站证书及长期稳定性仍待验证。

当前 EXE 已在仅系统 PATH、未预装 Python / Qt 的隔离环境中启动，检查关闭动画后的模型页面、本机模型 API 检测、设置页往返、窗口放大与退出；包内源码、界面资源和两种内核均通过校验。在本机 150% 缩放下，最大化后的客户区与屏幕工作区边界一致。打包方法见 [打包说明](PACKAGING.md)；动画测试与设备范围见 [性能记录](docs/animation-performance.md)。

## 从源码运行与打包

保留完整项目目录，安装依赖后启动：

```powershell
python -m pip install -r requirements.txt
pythonw tunnel_gui.pyw
```

源码运行时，缺少的穿透内核会从官方发布页下载并校验 SHA-256。发布的 EXE 包含内核，源码仓库不保存内核二进制。账户证书、隧道凭据和个人设置不随仓库或 EXE 分发。

重建 EXE 的依赖版本、步骤和校验方法见 [打包说明](PACKAGING.md)。

## 致谢

感谢 [FRP](https://github.com/fatedier/frp) 和 [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) 提供连接能力；设置图标采用 Google 官方 [Material Symbols](https://github.com/google/material-design-icons)，窗口控制按钮使用 [QWindowKit](https://github.com/stdware/qwindowkit) 官方 QML 示例及图标，并适配本项目主题。

第三方许可证及源码来源保存在 `third_party_licenses`、`assets/icons` 和 `qml/vendor/qwindowkit` 中，并随 EXE 打包。
