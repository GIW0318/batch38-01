# GSB Bugfix Task
## 题面
仇恨表接了多目标议会和回放后，换坦和转火全乱：治疗仇恨没按目标均摊，嘲讽只顶到 100%，仇恨转嫁可以连环，议会 boss 上天阶段仇恨还在涨，降仇恨只减当前目标，远程近战同系数，十秒后不衰减，同分顺序不稳，回放快照恢复后和原时间线不一致。aggro_ledger.py 的 ThreatTable 负责 add(actor, boss, value, kind, now)、taunt(actor, boss, now)、drop(actor, boss, pct)、link(src, dst, pct, until)、phase(boss, phase, now)、snapshot(boss)、rewind(snapshot_id, now)、top(boss, n) 和 state()。kind 系数直伤 1.0、治疗 0.5；治疗仇恨平分给以目标为目标的全部敌人；嘲讽顶到最高乘 1.1，10 秒内二次嘲讽只乘 1.05；drop 按 pct 减且不低于 0；link 最多三成，禁止二次 link，成环拒绝；air 阶段仇恨冻结，ground 恢复；超过 10 秒没仇恨每秒衰减 5%；snapshot 保存不可变向量，rewind 只在同阶段且 10 秒内有效，恢复后时间线要能继续；top 按仇恨降序、同分按最早达到；n 只允许 1 到 8；未知首领、负仇恨、时间回拨报错；state 给各首领最高、总仇恨、link 和快照 id 列表。十五条检查全红。

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
