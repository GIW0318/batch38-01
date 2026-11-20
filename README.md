# GSB Bugfix Task
## 题面
播放器接新时钟后音画不同步：视频走墙钟，音频按采样计数，缓冲低于 200ms 还播，漂移超 40ms 不修正，视频快了无限丢帧，音频慢了直接静音，暂停后时钟还在走，seek 不重置缓冲，倍速只改视频。av_sync_clock.py 的 AvClock 负责 push_video(pts, now)、push_audio(pts, now)、tick(now) 和 clock_view()。音频缓冲健康时以音频为主时钟，否则回退视频；启动缓冲 200ms；漂移超 40ms 时视频重复或丢帧，音频重采样比例夹在 0.98 到 1.02；暂停冻结；seek 清缓冲重置基准；倍速 0.5 到 2.0 同时作用两路；负 pts、时间回拨、未知倍速报错；tick 返回 action、漂移、缓冲深度；clock_view 给主时钟、漂移、丢帧计数。十五条用例眼下全红。

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
