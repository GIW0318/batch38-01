# GSB Bugfix Task
## 题面
世界事件日历上线后，两个活动同一分钟开、奖励发双份、跨时区玩家看到的时间不一样：事件区间重叠也排；阶段时长不校验；UTC 和本地时间混用；同一事件重复注册；取消后阶段还在跑；奖励结算按开始时间而不是结束时间；跨天事件被截断；状态返回内部日历。world_event_calendar.py 的 EventCalendar 负责 add(event, now)、phase(event_id, t)、cancel(event_id, now) 和 snapshot()。event 有 id、start、end、phases、timezone；区间不能重叠；phases 必须首尾相接且总时长等于区间；时间统一存 UTC，展示时再转；同一 id 重复注册报错；取消后 phase 返回 cancelled；奖励只在 end 后结算一次；跨天事件保留完整区间；start 大于等于 end、缺 phase、未知时区报错；snapshot 给事件数、各阶段计数、下一事件。十五条用例全红。

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
