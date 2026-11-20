# GSB Bugfix Task
## 题面
住宅区开放扩建后，家具穿墙：旋转 90 度占地没换宽高，两个家具重叠也放行，超出地块边界只裁一半，门朝墙里也能放，扩建后老家具坐标错位，删除不存在家具静默成功。housing_plot_grid.py 的 PlotGrid 负责 place(plot, item, x, y, rot)、move(plot, item, x, y)、remove(plot, item)、expand(plot, direction) 和 plot_view(plot)。初始 8 乘 8，最大 16 乘 16；item 有 id、w、h、door；rot 只允许 0、90、180、270，90 和 270 交换宽高；放置整块落在边界内且不重叠；door 必须朝向空地；move 原子完成，失败不改原位置；expand 只允许 east 和 south，不移动已有家具；同一 plot 最多 50 件；未知 plot/item、非法旋转、越界、重叠都报错；plot_view 返回占用格数、家具列表和门朝向。十五条断言全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：其他
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
