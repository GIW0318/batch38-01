# GSB Bugfix Task
## 题面
开放世界加了天气锋面后，两个相邻区域一个暴雨一个晴天，预报每十分钟翻一次，暴风警告提前量不够，读档后天气和历史对不上。weather_engine.py 的 WeatherEngine 负责 advance(now)、at(t)、forecast(t, horizon)、warning(t) 和 history(start, end)。构造给 world_seed、biome 和温度基线；锋面按 seed 确定性推进，每个 biome 的天气由锋面类型、地形和温度共同决定；状态 clear、cloud、rain、storm、snow，转移要满足 clear 到 cloud、cloud 到 rain 或 clear、rain 到 storm、storm 到 cloud、cloud 到 snow、snow 到 clear，且新状态持续 120 秒才确认，避免边界抖动；snow 只在温度不高于 0 时出现；forecast 返回覆盖 horizon 的区间列表，必须首尾相接，horizon 1 到 604800 秒；warning 在 storm 前 600 秒给出，置信度低于 0.7 不报；history 按时间回放，结果与 at 一致；时间回拨、未知 biome、负 horizon 报错；at 返回天气、剩余秒、锋面 id 和温度，history 返回。十五条用例眼下全红。

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
