# GSB Bugfix Task
## 题面
蜜罐蜜标扩到多租户后，告警几乎不能用：蜜标是递增编号一眼假，同一蜜标每次使用都告警，没有校验位，过期还告警，未知蜜标静默，来源和租户不记，没有去重窗口，撤销后还能用，四种蜜标同一严重度，轮换后旧蜜标仍无限期有效。honeytoken_ledger.py 的 CanaryLedger 负责 mint(family, keeper, ttl, ts)、rotate(family, ts)、touch(mark, caller, tenant, ts)、revoke(mark, ts)、report(window) 和 summary()。蜜标由 cnry_、family、24 位十六进制随机片段和 4 位 CRC32 组成；family 只允许 aws_key、url、doc、db，严重度 3、2、2、3；有效期 1 到 86400 秒；rotate 后旧蜜标保留十分钟宽限再失效；登记使用时先验校验位，未知或伪造报错；同一蜜标同一调用方十分钟内只告警一次；跨租户使用严重度加一；撤销返回 revoked 不告警，过期返回 expired；report 按蜜标聚次数、首末时间、租户集合；summary 只给数量、类型计数和告警数，不出现原始 secret。十五条断言全红。

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
