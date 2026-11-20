# GSB Bugfix Task
## 题面
远景 LOD 切换改成抖动后，画面出现棋盘格：4x4 Bayer 矩阵写错；抖动阈值没有按帧旋转；切换没有迟滞，距离边界来回跳；alpha-to-coverage 和普通混合混用；LOD bias 没有夹紧；静止时图案还在动；四级 LOD 阈值不单调；detail 透出内部数据矩阵。lod_dither.py 的 LodDither 负责 select(distance, lod_bias)、pattern(x, y, frame) 和 detail()。四级阈值是 30、60、120 米，带 5% 迟滞；bias 夹在 -1 到 2；抖动用 4x4 Bayer，帧号模 8 旋转图案；交叉淡化带是阈值的 10%；alpha-to-coverage 只在 MSAA 开启时用；静止帧图案必须稳定；负距离、非法帧号、非单调阈值报参数错误；select 返回当前级和混合系数；detail给出各级切换次数和当前 bias。十五条检查全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：图形渲染
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
