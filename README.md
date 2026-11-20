# GSB Bugfix Task
## 题面
采集节点改共享刷新后，脚本号把矿全抢了：同一玩家一轮反复采，工具等级不够也采，采空立即刷新，多人同时采超发，加成按等级线性加，时间回拨冷却变负，采空节点还显示可采。gathering_nodes.py 的 NodeField 负责 tap(node, player, tool_tier, ts)、respawn(ts)、lock(node, player, ts) 和 nodes()。node 有 id、charges、tier、respawn_at；每次 tap 扣 1，同玩家每轮只能一次，lock 可提前占用但 30 秒过期；tool_tier 不低于节点 tier；采空进 300 秒冷却，respawn 只处理到期节点并补满；工具每高一级产量加 10%，最多 50%；同一 ts 的并发 tap 按调用顺序扣层，0 层拒绝；重复采、工具不足、冷却中、未知节点、时间回拨都报错；nodes 给各节点剩余层、冷却剩余和占用者。十五条用例全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：其他
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
