# 一键内网穿透 · Elysia Tunnel GUI

想把本地跑着的小网站发给朋友看看，却又不想临时翻一堆命令？这个小工具就是干这件事的。

填个端口，点一下「开始穿透」，等外网地址出现，再复制给对方。

![主界面](docs/screenshot.png)

## 它能做什么

- **Cloudflare 临时隧道**：分享本地 HTTP / HTTPS 服务，不用先准备自己的服务器。
- **FRP 模式**：连接你自己的 FRPS，做 TCP 端口映射。
- **自动选择引擎**：HTTP / HTTPS 优先 Cloudflare，TCP 使用 FRP；填好 FRP 配置后，也可以作为自动模式的后备方案。
- 检测本机监听端口，显示外网地址、连接状态和实时日志。
- 自动从官方 GitHub 发布页下载缺失的内核，并校验 SHA-256。
- 一键停止、重启；最小化后继续运行，关闭窗口就停止穿透。

界面使用 **Python + Tkinter**，圆角控件和动画通过 Canvas 绘制。悬停、焦点、选项切换、点击波纹和连接状态都有动效，也会遵循 Windows 的动画开关。

## 怎么用

运行平台是 **Windows 10 / 11**，本机实测环境为 Windows 11、Python 3.12.14、Tcl/Tk 8.6.12。

准备一个包含 Tkinter 的 Python，把仓库下载到本地。`tunnel_gui.pyw` 和 `m3_ui.py` 要放在同一个目录；有 Python 文件关联时，双击入口即可启动，也可以运行：

```powershell
pythonw tunnel_gui.pyw
```

程序本身只用 Python 标准库，不需要额外安装 UI 框架。首次连接会下载对应内核，需要能访问 GitHub 和隧道服务。

本地网站或应用要先开启。比如它现在通过 `http://localhost:8080` 访问，就选 HTTP，填 `8080`，再点「开始穿透」。

**FRP 需要你自己的 FRPS 服务端。** 在「FRP 配置」里填好服务器、服务端口、远程映射端口及 Token，并确认服务器放行了映射端口。Token 不会作为明文配置保存到磁盘。

## 几件提前说清楚的小事

- Cloudflare 这里用的是**临时隧道**，适合演示和临时分享。重启后地址可能变化，不适合作为固定的网站入口。
- Cloudflare 临时模式支持 HTTP / HTTPS；其他 TCP 服务请选择 FRP。
- 「后台陪着你」是最小化到任务栏，**不是系统托盘或 Windows 服务**。退出软件后不会继续穿透。
- 分享出去的是你的本地服务。需要登录保护的内容，记得先在原应用里配好访问控制。
- Windows 安全软件可能拦截 FRP。本机测试中，Defender 将官方 FRP v0.71.0 标记为 `PUA:Win32/FRProxy`，阻止了执行；程序不会替你关闭安全软件。

## 实测到哪一步了

| 项目 | 结果 |
| --- | --- |
| GUI、端口检测、未监听端口提示 | 通过 |
| Cloudflare 下载及 SHA-256 校验 | 通过 |
| 公网 HTTPS → 临时隧道 → 本地 HTTP 测试服务 | 通过 |
| 停止、重启、关闭后的进程清理 | 通过 |
| 圆角控件、动画、键盘交互、小窗口滚动 | 通过 |
| FRP 下载及校验 | 通过；执行被本机 Defender 拦截 |
| FRP 实际转发、HTTPS 源站证书、长期稳定性 | 尚未验证 |

不是每一项都拿「理论上能用」冒充实测。上面没测到的，就先老老实实写在这里。

## 代码放在哪里

```text
tunnel_gui.pyw                # 程序入口、下载和穿透进程管理
m3_ui.py                     # 圆角控件、动画和界面文案
test_tunnel_environment.py   # 本机测试入口
docs/screenshot.png          # 界面预览
```

想调整动画节奏，可以改 `m3_ui.py` 的 `MOTION_DURATION_SCALE`，数值越大，动画越慢。当前是 `2.0`。

测试入口支持 `smoke`、`ui`、`download` 和 `e2e`。其中 `ui` 截图需要 Pillow；`e2e` 会短暂公开一个只返回固定文本的本地测试服务，并在结束后清理。测试截图只渲染应用自身窗口。

FRP 与 cloudflared 是各自独立的开源项目，内核不随此仓库分发。感谢 [FRP](https://github.com/fatedier/frp) 和 [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) 提供连接能力。

---

准备好啦？把端口告诉我，我们一起出发吧。♪
