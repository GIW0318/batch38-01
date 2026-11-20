# GSB Bugfix Task
## 题面
漏洞平台要同时出基础分、时间分、环境分和批量报告，评分器却只做关键词匹配：AV:N 和 AV:L 同分，S:C 时 PR 权重错，取整四舍五入，未知 metric 忽略，重复 metric 取最后，缺项用默认，temporal 混进 base，环境分不覆盖 base，批量里同一 vector 重复计算，策略变更后缓存不失效。cvss_engine.py 的 CvssEngine 负责 score(vector, profile)、batch(vectors, profile)、severity(score)、breakdown(vector, profile) 和 cache_stats()。按 CVSS v3.1 解析基础八项 AV、AC、PR、UI、S、C、I、A，每项必须出现且只能一次；temporal 的 E、RL、RC 和 environmental 的 CR、IR、AR、MAV、MAC、MPR、MUI、MS、MC、MI、MA 都要校验；环境指标覆盖对应基础指标后重算，时间分只乘时间因子；分数向上取到一位小数，范围 0.0 到 10.0；severity 边界 0、0.1 到 3.9、4.0 到 6.9、7.0 到 8.9、9.0 到 10.0；batch 按 vector 去重但保留出现次数，profile 变化让缓存失效；缺项、重复、未知项、非数字、非法组合都报错；breakdown 返回四个子分数；指标顺序不影响结果。十五条断言全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：漏洞检测与攻防
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
