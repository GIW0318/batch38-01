# GSB Bugfix Task
## 题面
任务目标共享后有人白嫖：击杀只有最后一击算，距离五百码也共享，同一怪重复计数，物品目标不消耗，放弃不回收进度，多阶段任务跳阶段。quest_objective_merge.py 的 ObjectiveMerge 负责 credit(quest, objective, player, amount, now) 和 progress()。任务有 stage 与 objectives；目标类型 kill、collect、interact；kill 要有 tag，interact 要在距离内；共享范围 100 码；每玩家对同一 source_id 只计一次；collect 交任务时扣物品；放弃只回滚自己未提交的进度；amount 必须是正整数；阶段按顺序推进，不能跳；未知任务、未知目标、超范围、负数报错；progress 给每玩家每阶段进度。十五条检查全红。

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
