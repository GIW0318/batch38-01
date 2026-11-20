# GSB Bugfix Task
## 题面
竞技场排队被骂：等十分钟范围还是一百，三排能排到单排，角色重复也能进，同人重复入队，取消后还在池里，匹配成功少人。arena_queue.py 的 ArenaQueue 负责 enqueue(team, now)、cancel(team, now)、match(now) 和 queues()。team 1 到 3 人且玩家不重复；初始分差 100，每等 30 秒放宽 50，最多 500；三排只配三排；角色组合按坦、奶、输出算相似度，缺奶降权；等待超 300 秒优先；重复入队、空队、重复玩家、未知队取消报错；match 取最合适一对并移出，没有合适返回 None，未匹配队伍保持原顺序；queues 给各分段人数与最长等待。十五条检查全红。

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
