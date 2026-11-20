# GSB Bugfix Task
## 题面
混音快照接进过场系统后，切场景时音量、声像和发送一起跳：快照只存了主音量，子 bus 的 send 没进快照；线性混合和等功率混合在不同 bus 上混用；t 超出 0 到 1 也照样算；自动化锁定的参数被快照覆盖；同名快照两次 capture 静默覆盖旧版本；切换过程中再次 apply 把中间态写进快照；场景结束时不能回滚到上一张；bus 层级里父 bus 的音量被重复乘；send 量在切换时溢出 1；detail 直接返回内部参数字典。mixer_snapshot.py 的 MixerRecall 负责 capture(name, buses, params, now)、blend(a, b, t, curve)、apply(name, bus, now)、schedule(name, at, curve)、rollback(steps) 和 detail()。bus 有 id、parent、gain、send、lowpass、locked 六个字段；参数范围 gain 0 到 1、send 0 到 1、lowpass 200 到 20000；capture 对每个 bus 存完整参数和版本号，同名 capture 版本加一且旧版本保留；blend 按 curve 的 linear 或 equal_power 计算，t 夹在 0 到 1；apply 只改未锁定 bus，父 bus 的 gain 只乘一次；schedule 在指定时刻进入目标快照，切换期间再次 apply 必须排队而不是覆盖中间态；rollback 按版本栈回退 N 步，最多到初始快照；send 超过 1 要软限幅而不是丢帧；未知快照/bus、负版本、参数越界、跨父链循环都报错；detail 给版本栈、当前 bus 参数和锁定项副本。十五条断言全红。

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
