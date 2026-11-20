# GSB Bugfix Task
## 题面
宠物改饱食度后，不是撑死就是饿死：同一种食物无限加好感，饱食度超过 100 还继续加，饿了不掉属性，死亡宠物还能喂，食物 buff 无限叠，玩耍可以连点。pet_feeding.py 的 FeedBowl 负责 give(pet, meal, ts)、tick(ts)、play(pet, ts) 和 pet_view(pet)。pet 有 id、hunger、happiness、alive；meal 有 id、nutrition、quality、cooldown、buff；每次喂食加 nutrition，hunger 封顶 100，超过拒绝；同种餐食 60 秒冷却；quality 1 到 5 的好感加成 1、2、3、5、8，不线性叠；每 10 分钟 hunger 掉 5，低于 20 时 happiness 每分钟掉 2；play 加 10 happiness 扣 5 hunger，冷却 120 秒；餐食 buff 持续 300 秒，同 id 刷新不叠层，最多同时 2 个不同 buff；喂错类别只加一半；死亡宠物拒绝所有操作；未知宠物/食物、负时间、冷却中操作都报错；pet_view 返回 hunger、happiness、buff 列表和冷却秒数。十五条用例眼下全红。

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
