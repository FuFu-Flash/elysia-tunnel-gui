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

Strata 负责运行本地模型，本工具分享模型 API，DeepSeek Harness 作为远程客户端。在运行模型的电脑上完成第 1–3 步，在使用 DSH 的电脑上完成第 4 步。

**先配置服务端密钥，再分享：Strata 设置 Key 并重启 → 在穿透软件输入同一个 Key，识别端口并通过验证 → 开始分享 → DSH 填写同一个 Key。** 只在 DSH 或网页中填写一串文字，不会开启服务端鉴权。

教程截图来自实际软件界面，使用演示数据：`local-model` 是占位模型名，`https://your-tunnel.example/v1` 是示例地址，不能直接使用。请以你自己的识别结果和分享地址为准。DSH 配图采用 0.2.0-rc.2，后续版本的菜单可能变化。

**临时隧道已实测可用于 DSH。** 此前使用 Cloudflare 临时地址，在真实 DSH 客户端中成功获取 Strata 模型列表并完成一次短回复，用户也补充确认临时地址可用。选择「临时地址」无需 Cloudflare 账户、自有域名或 FRPS 服务器。此前那次公网测试未启用 Strata 服务端鉴权，带密钥的公网鉴权流程仍待实测。

Cloudflare 官方仍列出 [Quick Tunnel 不支持 SSE](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/#limitations) 的限制。已有 DSH 对话成功记录，不能因此直接判断临时隧道无法用于 DSH；长回复、所有流式场景及长期稳定性仍需分别测试。临时地址重连后会变化。

### 1. 配置 Strata 服务端密钥，再启动模型

按照 [Strata 官方安装说明](https://github.com/Niko1221/Strata#install)完成安装和模型准备。Windows 的入口是 `START-HERE.bat`；Strata 的安装、模型下载与硬件要求由它的项目说明负责。

找到 Strata 安装目录中当前模型的 `strata-<model>.json`，例如 `strata-iq3_xxs.json`；文件位置见 [Strata 官方说明](https://github.com/Niko1221/Strata/blob/main/docs/INSTALL.md#where-things-are-stored)。用记事本或其他编辑器打开，在**最外层大括号内**加入下面这一项：

```json
"api_key": "REPLACE_WITH_YOUR_OWN_RANDOM_KEY"
```

将占位文字换成自己生成的随机长密钥。如果已经有 `api_key`，修改它的值即可，不要重复添加。保留原有配置，字段之间用英文逗号分隔；如果新增在最后一项，前一项末尾需要加逗号，新增项后不要加尾随逗号。这段只展示新增字段，不能用来覆盖整份文件。

保存后，停止当前 Strata 服务，再双击同目录对应模型的 `run-<model>.bat`，或通过 `START-HERE.bat` 启动同一个模型。**必须重启服务，刷新网页不会使密钥生效。** 保留 `127.0.0.1` 监听即可，穿透软件会连接本机服务。[服务端密钥说明](https://github.com/Niko1221/Strata/blob/main/docs/DETAILS.md#using-it)

等待模型就绪，打开 `http://127.0.0.1:8080`，点击「关于」查看接口地址与模型名称；如果改过端口，后续填写自己的端口。Strata 网页中的「API 密钥」是浏览器连接服务用的输入框，也应填写同一个 Key；它本身不会开启服务端鉴权。

![Strata 关于页面：确认本机 API 地址](docs/tutorial/strata-about.png)

*Strata 界面演示，模型与运行数据为占位内容。实际使用先完成上面的 JSON 密钥配置和服务重启；图中的网页输入框不能代替这些步骤。*

### 2. 自动识别模型 API，并开始分享

打开穿透软件的「模型分享」页面，程序会自动查找本机模型 API。开启鉴权的 Strata 服务会先显示「需要验证」。

**必须在穿透软件内输入 Key，完成验证后才能开始分享这个受保护的模型服务。** 在「指定本地端口」中填写 Strata 端口（默认 `8080`），在「模型服务已有的 API Key」中填写第 1 步配置的同一个 Key，点击「识别端口」。服务显示「已识别」并出现模型列表后，选择服务和模型。

首次配置时先核对密钥是否生效：用空 Key 或错误 Key 点击「识别端口」，应显示「需要验证」；再输入正确 Key 重新识别，应能读取模型列表。Strata 开启鉴权后，无 Key 或错误 Key 的 `/v1/models` 请求会返回 HTTP 401。如果错误 Key 仍能读取模型列表，先检查是否改了当前模型的配置、是否真正重启了服务，再开始分享；启动参数 `--api-key` 或环境变量 `STRATA_API_KEY` 可能覆盖 JSON 中的值。

![自动识别 Strata 的模型 API](docs/tutorial/elysia-detect.png)

*识别完成后的界面演示，Key 使用占位内容并被掩码。模型名称以实际列表为准。检测只读取模型列表，不加载模型、不发起推理；检测 Key 仅用于本次本机验证，随后清空，不会保存，也不会替 DSH 发送密钥。*

选择「临时地址」，点击「开始分享」，等待隧道连接成功。无需登录 Cloudflare，也无需购买域名。识别模型成功并不等于已经建立公网隧道。

如果已有 Cloudflare 托管的自有域名或 FRPS 服务器，也可以选择对应方式：固定域名需先在「设置」中完成授权和绑定，FRP 需先配置服务器与远程映射端口。使用临时地址无需准备这两种配置；固定域名和 FRP 的公网模型分享仍待实测。

### 3. 复制客户端连接信息

连接成功后，在「客户端连接」中点击「复制 Base URL」和「复制模型 ID」。临时地址的 Base URL 形如 `https://<分配的名称>.trycloudflare.com/v1`，必须保留末尾 `/v1`；模型名称直接复制，不要照抄截图中的 `local-model`。

![复制模型 API 地址与模型 ID](docs/tutorial/elysia-share.png)

*临时地址连接界面演示。图中的 `your-tunnel.example` 域名和连接状态均为占位内容；实际连接成功后，使用程序生成的 `trycloudflare.com` 地址。远程客户端不能使用服务端电脑的 `127.0.0.1:8080`。v0.4.0 界面保留「仅用于非流式」的旧提示；临时地址已有 DSH 实测成功记录，具体测试范围见上方说明。*

### 4. 在 DeepSeek Harness 中连接模型

安装并打开 [DeepSeek Harness](https://www.deepseek.com/en/download/)。在左下角进入「更多 → 设置 → 模型」，点击「添加模型提供商」，选择「自定义模型 API」。按下面填写：

| 字段 | 填写内容 |
| --- | --- |
| Provider ID | 例如 `strata-remote`；以小写字母开头，仅使用小写字母、数字和短横线 |
| 显示名称 | 例如 `Strata` |
| API 协议 | `OpenAI Chat Completions` |
| API 地址 | 上一步复制的 Base URL，保留末尾 `/v1` |
| API 密钥 | **必填：与 Strata 配置和穿透软件验证使用的 Key 完全一致** |
| 模型目录 / Model ID | 上一步复制的模型 ID，或获取可用模型后选择 |

![DeepSeek Harness 自定义模型提供商配置](docs/tutorial/dsh-provider.png)

*DSH 配置演示。示例地址不能使用，密钥必须填写自己在 Strata 服务端配置的 Key。穿透软件不会替 DSH 代填或发送 Key。API 协议选择 Chat Completions。*

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
| Cloudflare 临时地址 | 临时分享 HTTP / HTTPS 服务；已有 Strata → DSH 模型列表和短回复成功记录 | 已运行的本地服务和网络连接；分享模型 API 前先配置服务端密钥 |
| Cloudflare 固定域名 | 为服务使用自己的固定域名 | Cloudflare 托管的域名、账户授权及隧道绑定 |
| FRP | 通过自己的服务器进行 TCP 端口映射 | FRPS 服务器配置及可访问的远程映射端口 |
| 自动模式 | HTTP / HTTPS 优先 Cloudflare，配置 FRP 后可作后备 | 对应方式所需配置 |

固定域名不会自动换成临时地址。Cloudflare 真实账户授权、创建命名隧道、DNS 绑定和固定域名连通性尚未实测，见 [固定域名说明](docs/cloudflare-fixed-domain.md)。真实 FRPS 转发也尚未实测；模型分享中的 FRP 当前使用 HTTP，公网访问不加密。

隧道配置保存在本机，下次打开可继续使用，但不会自动启动连接。保存的 FRPS token 使用 Windows 用户级加密。

## 测试情况

本机 Windows 11 检查覆盖中英文切换、设置页往返、多隧道进程管理、FRPS 配置切换、托盘与退出清理，以及点击波纹、键盘操作、动画速度和关闭动画。窗口检查覆盖调整大小时位置不漂移、最大化使用屏幕工作区、还原后保留位置和尺寸。

本地模型识别与分享检查覆盖模型列表读取、检测 Key 的使用范围、客户端地址与示例复制、已有隧道配置保护、HTTP 转发及停止清理。此前通过 Cloudflare 临时地址完成 Strata 服务的公网模型列表读取和一次非流式请求；另在真实 DeepSeek Harness（DSH）Windows 客户端中获取模型并完成一次简短回复，用户随后也确认临时地址可用。

此前这次公网 DSH 测试未开启 Strata 服务端鉴权，证明的是连接与对话可用，不是正确 Key 通过、错误 Key 被拒绝的公网鉴权实测。上面的带密钥教程依据 Strata 的配置说明及本机代码核对；本次没有修改用户密钥、重启模型或新增推理测试。

已完成的 DSH 请求说明临时隧道在测试组合中可用，不代表所有模型、客户端、长回复、SSE 场景或长期运行已经验证。Windows 10、真实 FRPS 转发、Cloudflare 账户与固定域名操作、HTTPS 源站证书及长期稳定性仍待验证。

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
