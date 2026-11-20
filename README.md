# GSB Bugfix Task
## 题面
钥石副本改成路线和词缀组合后，结算全乱：词缀加时只看面板，死亡扣时不随次数递增，检查点奖励可以跳着领，队伍在副本里换人计时暂停，回城暂停能无限续，枯竭后还能继续打，通关升级层数按剩余时间四舍五入。keystone_ledger.py 的 KeystoneRun 负责 start(key_level, party, affixes, route, now)、checkpoint(node, now)、death(actor, now)、swap(old_member, new_member, now)、pause(now)、resume(now)、finish(now) 和 ledger()。基础时限按层数查表；词缀 bloodlust 加 120 秒、fortified 加 60 秒、grievous 让每次死亡额外扣 5 秒，且同类词缀不叠加；route 是检查点 DAG，必须按顺序到达，每个检查点给 15 秒奖励但只能领一次；死亡扣时按 5、10、15 秒递增，累计 5 次直接枯竭；swap 只能在暂停且回城，新成员不能重复，换人后死亡计数保留；pause 最多 180 秒，只能在检查点，resume 顺延截止时间；finish 时剩余超过 40% 升 2 层、超过 20% 升 1 层，否则 depleted；重复 start 或 finish、时间回拨、非法层数、空队伍、重复玩家都拒绝；ledger 给每名成员的奖励、死亡罚金和词缀影响副本。十五条断言全红。

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
