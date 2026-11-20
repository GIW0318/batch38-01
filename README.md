# GSB Bugfix Task
## 题面
坐骑换地形系统后，沙漠里耐力掉得比水里还快：不同步态消耗一样，地形系数没乘，跳跃不扣耐力，坠落不扣，体力见底还能冲刺，休息和走路回复一样，喂食没有冷却。mount_stamina.py 的 MountMeter 负责 ride(gait, terrain, seconds)、rest(seconds)、feed(item, ts)、jump(height) 和 mount_view()。gait 只允许 walk、trot、gallop、sprint，每秒消耗 1、3、8、15；terrain 系数 road 0.8、grass 1.0、sand 1.3、water 2.0；上限 100，低于 0 进入 exhausted，强制 walk 10 秒；jump 消耗 10 加高度乘 2，落地高度超过 3 额外扣 10；走路每秒回 1，rest 每秒回 5，feed 回 40 且冷却 60；上限变化时当前值截断；时间负数、未知 gait/terrain、冷却中喂食都报错；mount_view 返回当前值、上限、状态、地形和冷却剩余。十五条用例眼下全红。

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
