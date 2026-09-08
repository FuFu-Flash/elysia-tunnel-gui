# Cloudflare 固定域名

设置页新增 Cloudflare 登录入口、临时地址 / 固定域名切换、域名填写和创建绑定按钮。默认仍使用临时地址，只有用户主动点击才会打开授权或操作账户。

登录使用官方 `cloudflared tunnel login`，授权在浏览器中完成。应用不会接收 Cloudflare 密码。已有的本地 cert.pem 不会被覆盖；页面只能确认本地证书存在，不能凭此保证授权尚未过期。

创建绑定按钮会创建一个本地管理的命名隧道，并通过 `tunnel route dns` 给填写的域名添加 CNAME。需要已托管到 Cloudflare 的自有域名及相应账户权限。遇到已有同名记录不会强制覆盖。修改绑定域名不会删除旧 DNS 记录。

隧道身份会在 DNS 操作前保存；重试会复用已有本地凭据，避免 DNS 失败后重复创建。命名隧道启动时使用独立的 ingress 配置和 HTTP 404 兜底规则；本地 HTTP / HTTPS 服务通过固定 HTTPS 地址访问。固定域名连接失败时不会静默切换到临时地址或 FRP。

授权证书位于用户目录 `.cloudflared/cert.pem`。应用的隧道凭据位于 `%LOCALAPPDATA%/OneClickTunnelGUI/cloudflare/tunnel-credentials.json`，配置为同目录 `cloudflare.json`。这些凭据不放入仓库或 EXE。取消或退出会清理正在运行的授权/管理进程，已经创建的云端隧道及 DNS 记录会保留。

按用户要求，本次没有实际执行登录、创建隧道、DNS 绑定或固定域名连通性测试。只完成代码检查、界面检查和原有本地回归。

实现依据：[Cloudflare 官方本地管理隧道指南](https://developers.cloudflare.com/tunnel/advanced/local-management/create-local-tunnel/)。
