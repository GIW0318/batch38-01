# GSB Bugfix Task
## 题面
5.1 和 7.1 片源下混到立体声后，人声被埋：中置没按 0.707 混，环绕直接相加削顶，LFE 全增益，声道顺序按文件名猜，单声道转立体声只填左，采样率不一致静默截断，没有软限幅，未知布局崩，延迟不补偿。downmix_engine.py 的 DownmixEngine 负责 matrix(source, target)、apply(samples, source_rate, target_rate)、latency(source, target) 和 state()。布局支持 mono、stereo、5.1、7.1，声道顺序固定；5.1 转立体声时 FL 和 FR 原样，C 乘 0.707 分左右，SL 和 SR 各乘 0.707，LFE 乘 0.5；7.1 的 BL 和 BR 各乘 0.5；矩阵按行归一化到不超过 1；输出软限幅；单声道转立体声两路相同；采样率不一致时按比率线性插值并补偿滤波器延迟，比率限制 0.5 到 2.0；latency 返回每布局的样本延迟；未知布局、采样数不是声道整数倍、空输入、非法比率报错；state 给源布局、目标布局、矩阵、归一化系数和延迟副本。十五条断言全红。

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
