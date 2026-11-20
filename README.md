# GSB Bugfix Task
## 题面
参数自动化扩到多车道后，音量曲线会跳变：线性点之间走阶跃，hold 段不保持，指数曲线遇 0 崩，重复时间点取后一个，第一个点前返回 0，最后一个点后不保持，平滑没按时间常数，值超 0 到 1 也收，两个车道同时控制同一参数时层级乱。automation_lane.py 的 AutomationLane 负责 add(lane, point)、value(lane, t)、blend(lane_a, lane_b, t) 和 lanes()。point 有 time、value、curve，curve 只允许 linear、hold、exponential；点按时间排，重复时间报错；指数段两端都须大于 0；首点前和末点后保持端点值，hold 段返回左端点值；平滑时间常数 20ms；value 夹 0 到 1；车道按 layer 0、1、2 分层，layer 小的覆盖 layer 大的，同层后添加的覆盖；blend 按等功率曲线混合两条车道；负时间、非法 curve、NaN、未知车道都报错；value 按 48k 采样点精度返回；lanes 给各车道点数、时间范围、layer 和当前值。十五条断言全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：音视频处理
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
