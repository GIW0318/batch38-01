# GSB Bugfix Task
## 题面
MIDI 量化后鼓点全乱：note_on 和 note_off 分别量化把时长压成 0，swing 只影响奇数拍，三连音网格算成二等分，同音高重叠不处理，事件按字符串排序，PPQ 传 0 也收，负 tick 崩。midi_quantize.py 的 MidiQuantize 负责 quantize(events, ppq, grid, swing) 和 tracks()。事件有 tick、type、channel、note、velocity；先量化 note_on，note_off 按原时长平移且不早于 note_on；grid 支持 1/4、1/8、1/16、1/32 及三连音，三连音按 2/3 网格算；swing 50 到 75，偶数拍延后；同音高重叠时前一个 note_off 提前到新 note_on 前一 tick；按 tick、channel、note 稳定排序；PPQ 96 到 960；负 tick、非法 grid、velocity 越界报错；tracks 给事件数、量化偏移均值、重叠修正数。十五条用例全红。

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
