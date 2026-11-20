# GSB Bugfix Task
## 题面
定时任务双跑：旧持有者租约过期还在写，新持有者拿到的 fencing token 和上轮一样，下游挡不住旧写。fencing_lease.py 的 FenceLease 负责 acquire(resource, owner, now, ttl)、renew(token, now, ttl=None)、release(token)、validate(resource, token, now) 和 leases()。资源名先 casefold；token 是八位十六进制 epoch 加四位序号，同资源单调递增；空闲或过期才能 acquire，过期回收 epoch 加一；同一 owner 有效期内重复 acquire 返回原 token；renew 只对当前未过期持有者生效；release 只释放当前 token；validate 对过期、旧 epoch、错资源返回 False；ttl 1 到 3600 秒；时间回拨、未知 token、空资源名报错；leases 给每资源 epoch、持有者、到期时间。十五条断言全红。

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
