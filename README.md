# GSB Bugfix Task
## 题面
出口代理被拿去探内网：CONNECT 到 25 和 6379 也批，十进制和八进制 IP 绕过点分检查，IPv6 方括号解析错，userinfo 混在 authority 里，域名多一个点就绕过后缀，IDN 同形域直接过，DNS 解析到 127.0.0.1 仍放行，SNI 和目标不一致不管，header 塞 CRLF 也能过，回环和链路本地没拦。proxy_connect_guard.py 的 ConnectGuard 负责 authorize(method, target, headers, policy)、release(tunnel_id, now) 和 tunnels()。只收 CONNECT，authority 必须 host:port，缺端口按 443；端口白名单 443 与 8443；userinfo、空白、CR、LF、NUL 拒绝；主机小写去尾点、IDN 转 punycode；IP 识别十/八/十六进制和 IPv6；私网、回环、链路本地、组播默认拒绝，policy 显式允许才放；解析器返回的每个地址都要公网；SNI 必须等于目标；单客户端最多 4 条，空闲 300 秒回收；后缀按标签边界；tunnels 给活动隧道与拒绝原因计数。十五条断言全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：漏洞检测与攻防
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
