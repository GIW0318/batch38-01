# GSB Bugfix Task
## 题面
组队加职责锁定后开团乱：队长能邀自己，邀请过期还能接受，重复接受生成两个队员，队员能踢队长，队长掉线队伍解散，职责超出 1 坦 1 奶 3 输出还能进，准备检查有人没点也算过，两个邀请同时接受时容量被突破。roster_arbiter.py 的 RosterArbiter 负责 invite(leader, player, role, now)、accept(player, now)、decline(player, now)、kick(leader, player)、leave(player, now)、ready(player, flag)、start(leader, now) 和 state()。最多 5 人，职责上限坦 1、奶 1、输出 3；邀请 60 秒过期，单玩家只有一个待处理；accept 时校验职责容量，并发接受只能一个成功；只有队长能踢且不能踢自己；队长离开按加入时间转给最早成员，并发离开只生效一次；准备 30 秒，全 ready 才能 start；掉线保留 120 秒宽限，宽限内占位但不可准备；满员、职责超限、非队长、过期邀请都报错；state 给成员、职责、准备状态、队长和宽限到期时间副本。十五条断言全红。

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
