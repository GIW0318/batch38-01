# GSB Bugfix Task
## 题面
双天赋上线后，洗点和装备加成开始互相污染：两个天赋树共用已用点数，装备加成的点数被当成已花点数，免费洗点窗口按账号而不是按天赋算，洗点退还顺序反了导致前置先退、后面的点还在，战斗中可以读档换天赋，读档失败留下半套点。talent_respec.py 的 TalentGrid 负责 spend(spec, node, points)、respec(spec, ts, free=False)、save_build(name, spec)、load_build(name)、set_gear_bonus(points) 和 view(spec)。每个 spec 独立，7 层，点下一层前前面各层累计至少 5 点乘层数；单节点不超 max_rank，前置 requires 必须满；总上限 51 加装备加成，装备加成只提高上限不占已用；respec 按投入逆序退还，费用按已用点乘 50 金币并随 30 天免费窗口衰减，free 只在窗口内生效；in_combat 时 respec 和 load_build 都拒绝；save_build 存点数分配和 gear_bonus 快照，load_build 先整体校验再原子替换，失败不改当前状态；未知 spec/node、负点数、超上限、前置不满、重名存档都报错；view 返回每层已用、剩余、上限和可洗点费用。十五条用例全红。

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
