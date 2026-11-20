# GSB Bugfix Task
## 题面
描边改成 SDF 后图标出现双重轮廓：圆和矩形距离函数写错，并集把内部距离也加，差集顺序反，描边宽度按像素写死，平滑为 0 出现硬边，重叠处 alpha 叠加，采样越界返回 0 导致整屏描边。sdf_outline.py 的 SdfOutline 负责 build(shapes)、sample(x, y) 和 bounds()。图形支持 circle、rect、segment，op 支持 union、subtract、intersect；距离用解析式；描边宽度和平滑半径可配；alpha 是 smoothstep 后的覆盖；差集只减不并；重叠先并再描边；包围盒外采样返回大正数；未知图形、负半径、负宽度、空集合报错；bounds 给图形数、包围盒和描边参数。十五条检查全红。

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
