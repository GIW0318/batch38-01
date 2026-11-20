# GSB Bugfix Task
## 题面
显存分配器换新后低端机闪退：大小块同 size class，超预算还分配，碎片率不算，淘汰只看创建时间，transient 不能别名，double free 静默，未知句柄崩，defrag 挪走正在采样的块。gpu_memory_budget.py 的 GpuBudget 负责 alloc(size, kind, tag)、free(handle)、defrag(now) 和 usage()。size class 从 256B 到 64MB 按 2 的幂；总预算可配，超了先按优先级淘汰再拒，无可淘汰返回失败；碎片率等于空闲块数除以总块数；transient 可共享同块；double free、未知句柄、负 size 报错；defrag 只动未 pin 的块；alloc 返回句柄、偏移、实际块大小；usage 给已用、峰值、碎片率和各 kind 占用。十五条检查眼下全红。

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
