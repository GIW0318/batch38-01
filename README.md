# GSB Bugfix Task
## 题面
贴花上线后弹孔会飘：投影只用世界坐标不看朝向，斜面和背面也投，池满直接覆盖在用槽，生命周期到了不回收，同位置多个贴花顺序每次不同，透明边缘没按角度淡出，深度偏移太小 z-fighting。decal_projection.py 的 DecalPool 负责 add(decal, now)、project(point) 和 decals()。decal 有 id、position、normal、size、rotation、lifetime、priority；沿法线盒投影，入射角超 60 度淡出到 0；背面拒绝；池容量 64，满了先淘汰低优先级再淘汰最旧；lifetime 到期由 expire 回收；同位置按 priority 再按创建时间；深度偏移取尺寸 0.1%；尺寸 0、法线为零、负 lifetime 报错；decals 给活动数、淘汰数、池快照。十五条检查眼下全红。

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
