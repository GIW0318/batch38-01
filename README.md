# GSB Bugfix Task
## 题面
注册接口被脚本刷，加了工作量证明却没用：challenge 取时间戳可预测，nonce 只查数字，前缀零位不看，同解重复提交也过，过期 challenge 还能用，difficulty 传 0 也发，单客户端挂几十个未完成，失败不累计难度不变，nonce 负数、字符串、超 2^32 都收，计算拼 challenge_id 不拼原文。pow_challenge_gate.py 的 PowGate 负责 issue(client, now, difficulty=None)、verify(client, challenge_id, nonce, now) 和 challenges()。challenge 由 secret、client、序号、now 做 SHA-256；nonce 是 0 到 2^32-1 的整数，sha256(challenge 拼冒号拼十进制 nonce) 前导零位不少于 difficulty；默认 16，连续失败加 2，成功减 1，夹 12 到 24；120 秒有效，只消费一次，单客户端未完成最多 3 个；重复消费、未知 id、负难度、难度超 32 报错；verify 成功给剩余尝试与耗时，失败给原因；challenges 给各客户端未完成数与难度。十五条检查全红。

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
