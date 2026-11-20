# GSB Bugfix Task
## 题面
网关上周被慢连接打满，排查下来 RequestBudget 只记了总时长：客户端每 9 秒发一个 header 字节，10 秒的 header deadline 永远不触发；body 阶段一字节一字节发，没有最小速率约束；header 超过 64KB 才拒绝，实际 16KB 就该掐；100-continue 还没请求就直接收 body；同一条连接上 pipeline 了五个请求也不计数；连接空闲两小时不回收；finish 之后计数没有减；时间戳回拨时 deadline 算成负数；重复 open 同一连接直接覆盖旧状态。slow_request_budget.py 的 RequestBudget 负责 open(conn, ip, ts)、recv_headers(conn, bytes, ts)、recv_body(conn, bytes, ts)、finish(conn, ts) 和 profile()。header 必须在 10 秒内完成且累计不超过 16KB；body 进入后前 5 秒免检，之后按每秒 1KB 的最低速率算，累计上限 1MB；只有显式声明 100-continue 的连接才允许在 header 后等待；每条连接最多 pipeline 2 个请求；空闲 30 秒回收；单 IP 并发 8 条、全局 100 条；任何方法返回 ok 与 reason，超限不抛异常，但 finish 未知连接、时间回拨拒绝受理；profile给出各 reason 的计数和当前连接数。十五条用例一条也过不了，别去改断言。

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
