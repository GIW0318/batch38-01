# GSB Bugfix Task
## 题面
钓鱼玩法改成按条件出鱼后，玩家在同一个点钓到的全是垃圾：天气、时段、水深、饵料都没参与权重；稀有鱼在错误季节也出；连竿没有保底；鱼竿等级只影响速度不影响鱼种；同一钓点被脚本占满没有冷却；脱钩率写死；鱼王没有全服上限；状态返回内部权重表。fishing_conditions.py 的 FishingSpot 负责 cast(player, spot, bait, rod, now)、resolve(cast_id, seed) 和 snapshot()。条件有 weather、season、hour、depth、bait、rod；每类鱼有权重表，权重乘算后归一化；稀有鱼限制季节和时段；连续 10 次未出稀有触发保底，保底后计数清零；鱼竿等级只加成功率，不改鱼种；同玩家同钓点 30 秒冷却；脱钩率按鱼种难度和鱼竿差算；鱼王每服务器每天 1 条；未知天气、季节、饵料报错；resolve 用 seed 确定性；snapshot 给钓点占用、各鱼种计数、保底进度。十五条用例全红。

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
