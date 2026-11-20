# GSB Bugfix Task
## 题面
远景树换 impostor 一转身就闪：八方向切换没交叉淡化，atlas 网格算错裁掉最后一列，透明边缘没 dilation 采到黑边，法线编码坐标系错，LOD 阈值没迟滞，深度偏移导致穿插，视图数不是 8 或 16 也收。imposter_bake.py 的 ImposterBaker 负责 render_views(mesh, views, atlas)、select(camera) 和 atlas_view()。views 只允许 8 或 16，绕 Y 均匀采样；atlas 按 ceil(sqrt(views)) 分格，每格 2 像素 padding；alpha 覆盖低于 0.1 丢弃；法线八面体编码；LOD 按屏幕高度切换，阈值 10% 迟滞；深度偏移取包围盒半径 1%；select 返回帧索引与混合权重，无视图返回 -1；视图数非法、空 mesh、atlas 太小报错；atlas_view 给版本、帧数、图集占用。十五条检查全红。

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
