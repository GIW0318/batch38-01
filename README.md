# GSB Bugfix Task
## 题面
主城换周轮班后，NPC 在错误时间出现在错误地点：跨天巡逻段被算成负时长，周三的日程套到周四，天气覆盖和基础日程同时生效，战斗打断后从当天开头重来，恢复时已经过了下一段还停在旧段，导出计划被外部改坏。npc_schedule.py 的 ScheduleBoard 负责 assign_week(npc, week_plan)、override(npc, window, activity, priority, ts)、status(npc, t)、interrupt(npc, reason, t)、resume(npc, t) 和 export()。week_plan 是 7 天的段列表，每段有 start、end、waypoint、activity，跨天允许，同一天内不能重叠，activity 只允许 idle、patrol、trade、sleep、eat；override 只在该窗口生效，priority 1 到 3，高优先级覆盖低优先级，同优先级取更晚创建；override 不能跨周界；interrupt 记录当前段偏移和原因，resume 从断点续，若已过段尾则推进到下一段；status 返回当前活动、来源 base/override/interrupted、waypoint、剩余秒和下一次切换；t 必须非负；未知 NPC、重叠、非法活动、无打断记录 resume、越界窗口都报错；export 返回周号和各 NPC 计划。十五条断言全红。

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
