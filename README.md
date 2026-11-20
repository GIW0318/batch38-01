# GSB Bugfix Task
## 题面
渲染状态缓存越缓存越慢：blend 因子和方程没进哈希，depth write 和 func 漏了，cull 不同也命中同一状态，color mask 没算，pass 切换不失效，重复绑定不计数，LRU 满了不淘汰，默认状态被改，状态统计只给命中率。blend_state_cache.py 的 BlendCache 负责 get(desc)、bind(desc, ts)、invalidate(pass_id) 和 stats()。desc 有 blend_src、blend_dst、blend_op、depth_test、depth_write、depth_func、cull、color_mask 八个字段；哈希覆盖全部字段；同 desc 重复 bind 记 redundant；pass 变化通过 invalidate 清空该 pass 的缓存；容量 256 按最近使用淘汰；默认状态单独一槽；未知枚举、缺字段、负容量报错；get 返回句柄，bind 返回是否真正切换；stats 给命中、未命中、冗余、淘汰、各 pass 条目数。十五条断言全红。

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
