# Windows EXE

`dist/ElysiaTunnel.exe` 是 Windows 10/11 x64 单文件程序，双击即可运行。

包含 Python、PySide6 / Qt、QML 界面、多尺寸应用图标、Visual C++ 运行库，以及经过 SHA-256 校验的 cloudflared 2026.8.3 和 frpc v0.71.0。不需要预装 Python、Qt 或手动安装穿透内核；联网仅用于建立隧道。FRP 仍需自己的 FRPS 服务器配置。

单文件启动时会把运行资源展开到系统临时目录，退出后由打包运行器清理。外观设置、隧道和 FRPS 配置保存在 LocalAppData 中，不随 EXE 分发。保存的 FRPS token 使用 Windows 用户级加密，不适合直接复制配置文件到其他用户账户使用。

## 重建

安装 `requirements.txt` 与 PyInstaller 6.22.2。将校验过的 amd64 内核和对应 JSON 清单放入 `bundled_engines`，保留 `assets`、`qml` 和 `third_party_licenses`，运行 `python build_exe.py`。

构建脚本主动隔离 PATH，避免其他工具目录中的同名 DLL 混入。之前的独立启动测试曾检出 Poppler 的 ICU 被误收集，因此构建后必须在空工作目录、仅系统 PATH 下验证 EXE，而不能只测试源码启动。

第三方许可证及源码来源一并嵌入程序包。应用图标使用用户提供的原图，仅进行 ICO 格式和尺寸转换。
