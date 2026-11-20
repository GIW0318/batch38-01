# GSB Bugfix Task
## 题面
阴影级联一升级，远处影子就抖：相机一动边界跳，光源方向每帧微调导致重投影，分割比例写死，最后一级没盖住远平面，级联间没过渡带，光源在相机背后时包围盒算反，正交范围没按视锥角点求，texel 没对齐。shadow_cascade_fit.py 的 CascadeFit 负责 splits(camera)、fit(light, camera) 和 cascades()。三级比例 0.1、0.3、0.6，最大距离取远平面；每级正交范围由视锥角点变换到光源空间求包围盒；光源方向量化到 1 度、中心按 texel 对齐；相邻级联留 10% 重叠；最后一级覆盖远平面；近平面大于远平面、光源方向为零、负距离报错；splits 返回递增三段；cascades 给每级范围与 texel 大小。十五条用例一条也过不了。

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
