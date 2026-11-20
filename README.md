# GSB Bugfix Task
## 题面
战斗日志的 DPS 统计和游戏内对不上：宠物伤害挂在宠物名下，dot 记给最后一跳的人，吸收盾被当成伤害，同一条事件导入两次会翻倍，团灭后不重新分段，uptime 按整场算，暴击率把 dot 也算进去。combat_log_fold.py 的 CombatFold 负责 ingest(events)、summary(encounter_id) 和 totals()。事件字段是 id、t、source、target、ability、amount、type、crit、overkill；宠物按 pet_owner 归主人，dot 归最初施法者，absorb 不计伤害，按 id 去重；boss 进场开段，团灭或击杀收段；uptime 只算目标活着的时间；暴击率只统计直伤。summary 给出总伤、DPS、技能占比、暴击率和过量；时间倒序、负伤害、未知类型都报错；totals 返回事件数与段数。十五条断言全红。

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
