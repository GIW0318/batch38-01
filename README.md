# GSB Bugfix Task
## 题面
团本换分层减伤后，坦克和治疗互相甩锅：护盾不分伤害类型，伤害转移可以链式触发，持续伤害每跳重新算减伤，无敌帧挡不住 dot，过量伤害把治疗统计撑爆。damage_pipeline.py 的 DamagePipeline 负责 hit(target, amount, dtype, source)、shield(target, amount, until, dtype, priority)、redirect(target, to, pct, until)、tick(ts) 和 snapshot(target)。结算顺序是转移、穿透、抗性、护甲、护盾、生命；转移最多 50% 且不能再转移，形成环直接拒绝；抗性上限 70%，护甲减伤 armor/(armor+100) 上限 75%；护盾按 dtype 吸收，同类型多张按 priority 再按到期时间；dot 在施加时快照每跳减伤值，之后属性变化不影响；无敌帧 1 秒免疫直伤但不免疫已有 dot；过量伤害截到当前生命并单独统计；负数、零伤害、未知 dtype、过期护盾、非法转移都报错；tick 清过期护盾和转移；snapshot 返回生命、护盾列表、dot 列表和减伤明细。十五条用例全红。

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
