# GSB Bugfix Task
## 题面
竞技场选人阶段总出重复：同一英雄两边都能选；ban 位和 pick 位混用；超时自动选第一个；双方同时提交冲突；角色重复不校验；选完还能改；重赛不重置；选人视图会暴露英雄池。arena_draft.py 的 DraftRoom 负责 ban(team, hero, clock)、pick(team, hero, clock)、timeout(clock) 和 draft_view()。每方 3 ban、5 pick，英雄池不能重复；ban 先于 pick，顺序是 A ban、B ban、A pick、B pick 两轮；同一英雄被 ban 或被选后不可再用；每步 30 秒，超时自动从剩余池按 id 升序取第一个；双方同时提交按时间戳早的生效，另一条报冲突；角色至少 1 坦 1 奶，缺角色拒绝开始；选完不能改；重赛清空并换边；未知英雄、重复选择、顺序错误报错；draft_view 给双方 ban/pick、剩余时间、当前步骤。十五条断言全部飘红。

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
