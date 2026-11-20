# GSB Bugfix Task
## 题面
公会战结算被投诉：重复占领重复给首占奖励，最后十分钟双倍没生效，投降后还加分，平局按公会名倒序，时间回拨算出负分，未知据点直接崩。guild_war_score.py 的 WarLedger 负责 capture(node, guild, now)、tick(now)、surrender(guild, now) 和 standings()。据点有 id、points、owner；首占加 50，同公会重复占不再给；每满 60 秒按归属加分，最后 10 分钟乘 2；投降立即结束，之后 tick 不再加；总分相同先比据点数，再比最早占领时间；未知据点、空公会、时间回拨、tick 传负数报错；tick 对同一分钟幂等；standings 给总分、据点数、剩余时间和结束标记。十五条断言全红。

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
