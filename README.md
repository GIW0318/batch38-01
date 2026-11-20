# GSB Bugfix Task
## 题面
团队增益按小队分配后，Buff 互相顶：同组两个萨满插同一根图腾，图腾槽超 4 个也收，增益过期不补，重复刷新把剩余时间清零，距离超 40 码还算覆盖，职业缺失没兜底，同类别 Buff 不互斥，移除后覆盖不重算。buff_ledger.py 的 BuffLedger 负责 place(group, buffs)、refresh(now)、remove(group, buff_id)、recompute(now) 和 coverage(now)。团队 5 队每队 5 人；buff 有 id、category、duration、range、class、totem、rank；同队同 category 只能一个，rank 高的覆盖低的；萨满图腾每队最多 4 个；刷新只在剩余 30 秒内延长到 600 秒，否则不叠加，且只对已生效 buff 生效；超 range 不覆盖；职业缺失用同类替代；remove 只移除指定 buff 并重算覆盖；重复 buff、图腾超限、未知职业、负时间报错；coverage 返回每队生效 buff、剩余时间、覆盖人数和缺口副本；recompute 必须幂等。十五条断言全红。

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
