# 教程配图 / Tutorial screenshots

这些图片用于 README 的 Strata → Elysia Tunnel → DeepSeek Harness 教程。截图来自实际软件界面，使用演示数据；`local-model` 和 `https://your-tunnel.example/v1` 均为占位内容，不能直接用于连接。

| 图片 | 内容 | 拍摄范围 |
| --- | --- | --- |
| `strata-about.png` | Strata「关于」页面与本机 API 地址 | 实际网页界面，注入演示元数据；未加载模型或发起推理 |
| `elysia-detect.png` | Elysia 自动识别后的服务与模型列表 | 独立配置，演示模型元数据；未连接真实模型服务 |
| `elysia-share.png` | 分享后的 Base URL 与复制按钮 | 演示域名与连接状态；未建立公网隧道 |
| `dsh-provider.png` | DSH 自定义模型 API 表单 | 示例地址与占位密钥，不含真实凭据 |
| `dsh-model.png` | DSH 模型下拉列表 | 独立测试配置，提供商注明「本地演示」 |
| `dsh-chat.png` | DSH 发送消息并收到回复 | 实际 DSH 调用本机模拟接口；未调用真实模型或公网隧道 |

DSH 截图版本：0.2.0-rc.2。拍摄日期：2026-10-08。

The screenshots show real application interfaces with demonstration data. `local-model` and `https://your-tunnel.example/v1` are placeholders. The Elysia connection state is simulated, and the DSH reply comes from a local mock API. No screenshots contain real credentials or establish a new public Strata inference test. DSH version: 0.2.0-rc.2. Captured on 2026-10-08.
