# GSB Bugfix Task
## 题面
附魔叠加改版后，武器能叠三个同效果：同组不互斥，超三层也收，叠层收益不递减，诅咒能直接移除，物品等级不够也能附，重复附魔不合并，移除不存在的静默成功。enchant_scroll.py 的 EnchantStack 负责 apply(item, enchant, ts)、remove(item, enchant, ts) 和 item_view(item)。item 有 id、level、slots，武器 3 槽、护甲 2 槽；enchant 有 id、group、tier、curse、duration；同 group 互斥；同 id 最多 3 层，收益 100%、50%、25%；tier 不高于等级除以 10；curse 不能 remove，到期自动消失；槽位不足、重复超限、组冲突、等级不足、移除不存在都报错；apply 返回总收益和剩余槽位，remove 返回剩余层数与收益；item_view 给附魔列表、总收益和到期时间。十五条用例全红。

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
