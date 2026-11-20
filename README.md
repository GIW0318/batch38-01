# GSB Bugfix Task
## 题面
波形缩略图改增量缓存后，拖动时间轴看到旧峰值：奇数长度尾块丢了，多声道混成一个，level 0 不是原始采样，局部更新只改 level 0 不改上层，查询和更新并发时读到半新半旧，查询越界不报错，min/max 顺序反，削波只看绝对值大于 1，淘汰把正在查询的级清掉。peak_cache.py 的 PeakCache 负责 build(samples, channels, block)、update(start, samples, channels)、query(start, end, level, channel)、evict(budget_bytes) 和 stats()。samples 交错浮点；level 0 每块大小 block，之后每级翻倍；每块每声道存 min/max；尾块不足也保留；update 重算受影响块并向上合并到所有级，版本号递增；query 读取一致版本，不能看到部分更新；level 0 到最大级；start 小于 0、end 超长、start 大于 end 报错；block 只允许 64、128、256、512；削波阈值 1.0，等于也算；evict 只淘汰最冷且未被查询占用的级，低于 level 0 不淘汰；stats 给级数、总块数、内存、版本和查询计数副本。十五条断言全红。

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
