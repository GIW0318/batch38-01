# GSB Bugfix Task
## 题面
边界按 TLS 指纹封禁后误伤严重：同一个客户端每次握手 JA3 都不同，GREASE 被算进去，cipher 列表被排序，重复扩展没去重，SNI 扩展位置进了列表，TLS1.3 supported_versions 处理错，空列表拼成 None，MD5 大小写不统一，长度畸形崩，未知版本默认 771，allowlist 前缀匹配误放，同一指纹两条策略取第一条。ja3_fingerprint.py 的 Ja3Index 负责 parse(hello)、fingerprint(hello)、match(policy)、add_policy(entry) 和 catalog()。hello 有 version、ciphers、extensions、curves、point_formats；先剔 0x0a0a、0x1a1a 这类 GREASE，保序；SNI、ALPN、padding 不参与；重复扩展留第一次；JA3 串按版本、cipher、扩展、曲线、点格式用逗号连字符拼，空列表用空串，最后小写 MD5；version 缺失或不在 769 到 772 报错；长度非偶数、超 64 扩展、负数报错；match 只做 MD5 精确匹配，策略支持 allow、deny、challenge 和 min_version，重复 MD5 拒绝，未命中给 default；add_policy 校验动作和版本；catalog 给指纹数、命中数、拒绝数。十五条断言全红。

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
