# GSB Bugfix Task
## 题面
赛季末排行榜一堆僵尸号，运营要求加衰减，RatingBook 现在只加不减：三十天不打的人分数原封不动；每周该扣多少没定；新手前十场和老人用同一个 K；同一个人能同时出现在两队；重复报同一场比赛分数涨两次；分数能扣成负数；report 里未知玩家直接 KeyError；衰减重复执行会多扣；book 交出内部对象字典。pvp_rating_decay.py 的 RatingBook 负责 register(player, at)、report(winner_team, loser_team, at)、decay(at)、rating(player) 和 book()。队伍 1 到 5 人且不能重复，跨队重复返回失败；Elo 期望按 400 分差算，前 10 场 K 取 64，之后取 32，多人队按平均分结算后每人加减同样的值；report 同一对队伍同一 at 只算一次；衰减在 30 天未活动后触发，每满 7 天扣 25，单次最多扣 200，分数下限 0；decay 对同一周幂等；register 重复只更新登录时间；rating 未知玩家返回 None；负分、空队伍、时间回拨返回失败；book给出玩家数、已衰减数和分数快照。十五条断言眼下全红。

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
