# GSB Bugfix Task
## 题面
帧预算工具把优化方向带反了：单帧尖刺被均值吃掉，p95 当成最大值，各 pass 平均分预算，降分辨率没迟滞，升档要等太久，尖刺只看一帧。frame_budget_governor.py 的 FrameGovernor 负责 record(pass_name, ms, frame)、target(now) 和 budget()。每个 pass 留最近 60 帧算均值与 p95；单帧超均值 2 倍且连续 3 帧才算尖刺；总预算 16.6ms，渲染 60%、逻辑 25%、其他 15%；缩放 0.5 到 1.0，连续 3 帧超预算降档，连续 120 帧稳定升档；降档先砍低优先级 pass；负耗时、未知 pass、重复 frame 报错；target 给当前缩放和建议砍的 pass；budget 给各 pass 均值、p95、尖刺数。十五条用例一条也过不了。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：图形渲染
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
