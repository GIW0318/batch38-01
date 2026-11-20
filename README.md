# GSB Bugfix Task
## 题面
容器挂载基线扫描漏掉一堆逃逸面：hostPath 挂根目录也放行；propagation 是 rshared 不报；/proc、/sys、/dev 没掩蔽；docker.sock 挂进去算低风险；只读标志只看字符串；nosuid、noexec、nodev 缺一个不扣分；同一目标重复挂载取最后一条；符号链接指向宿主目录不解析；状态返回内部挂载表。container_mount_check.py 的 MountInspector 负责 inspect_spec(spec)、evaluate(policy) 和 snapshot()。spec 有 source、target、read_only、propagation、options；source 先做 realpath，禁止宿主根、/etc、/var/lib、/proc、/sys、/dev；target 必须在容器内且不重复；propagation 只允许 private、rprivate；read_only 必须是布尔真；options 必须含 nosuid、noexec、nodev 中策略要求项；docker.sock 记 critical；符号链接解析后再判；未知字段、重复 target、空 source 报错；evaluate 给 problem 列表和分数；snapshot 给挂载数、critical 数、分数。十五条检查全红。

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
