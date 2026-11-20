# GSB Bugfix Task
## 题面
三份 SARIF 合并后规则名和行号全串：ruleIndex 用最后一份 run 的表，ruleId 大小写不同算两条，uriBaseId 没展开，region 缺 startLine 也收，partialFingerprints 冲突随机取，同一问题两次 run 重复，suppression 被忽略，level 映射乱，file:// 和反斜杠没归一，baselineState 不参与，一条坏 result 整批失败，空 runs 崩，工具版本不校验。sarif_fold.py 的 SarifFold 负责 merge(runs)、dedupe()、summary() 和 merge_report()。只收 2.1.0，run 必须有 driver.name 和 version；ruleIndex 只在当前 run 解析，越界回退 ruleId；uriBaseId 用 originalUriBaseIds 展开，URI 去 file://、反斜杠转斜杠、百分号解码、折叠点段；去重优先 partialFingerprints，其次 ruleId 加 URI 加 startLine；level 映射 error 到 high、warning 到 medium、note 到 low、none 到 info；accepted 或 underReview 的 suppression 不入库；baselineState 保留；坏 result 跳过计数；summary 按严重度给数量和 top 规则；merge_report 给 run 数、结果数、跳过数。十五条检查全红。

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
