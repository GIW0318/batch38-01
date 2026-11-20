# GSB Bugfix Task
## 题面
悬赏板一个人接十个任务：接取上限没生效，自己的悬赏也能接，等级不够也接，过期还能完成，重复完成给两次奖励，组队奖励不分，放弃不释放名额。bounty_board.py 的 BountyBoard 负责 post(contract, now)、claim(player, contract_id, now)、complete(player, contract_id, now)、expire(now) 和 board_view()。contract 有 id、poster、target、reward、min_level、max_claims、expires_at；每人同时最多 3 个；不能接自己发的；低于 min_level 拒；claim 后 600 秒未完成自动释放；完成只能接取者提交，奖励按队伍人数均分，余数给队长；过期、重复完成、超 max_claims、未知合同报错；expire 标记到期；board_view 给开放、进行中、完成、过期数量。十五条用例眼下全红。

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
