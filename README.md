# GSB Bugfix Task
## 题面
法线烘焙换新工具后，模型接缝处出现黑线：cage 射线起点没有沿法线偏移；最大距离不限制，打到背面；切线基按世界坐标算而不是 UV；UV 接缝两侧的法线被平均；padding 没有扩边；绿通道方向可配但没生效；射线未命中写零向量；采样数超过 64 也接受；退化 UV 直接崩；inspect 交出内部对象。normal_bake_cage.py 的 NormalBaker 负责 bake(high, low, cage, samples) 和 inspect()。cage 射线从低模顶点沿法线偏移开始，最大距离取 cage 厚度的 2 倍；切线基用 UV 导数算；只在同一 UV 岛内平均；padding 默认 2 像素；绿通道可翻转；未命中回退低模法线；samples 1 到 64；退化 UV、空 mesh、cage 与低模顶点数不一致返回失败；bake 返回法线贴图和未命中数；inspect给出分辨率、采样数和未命中率。用例目录下的验收脚本十五条检查全红。

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
