# GSB Bugfix Task
## 题面
漏洞排期在季度审计里被打回：同一 CVE 在不同包被合并，1.0.10 被判低于 1.0.2，KEV 清单过期后还按 critical 算，不可达漏洞也催生产 SLA；例外审批人写成申请人自己也能过；负责人手上挂了三十条还继续派；关闭后同键重现没有重开；工作日把法定假日算进去；队列把逾期数算成 0。vuln_triage_sla.py 的 VulnTriage 负责 ingest(findings, clock)、assign(id, owner, clock)、request_exception(id, until, approver, clock)、approve_exception(id, approver, clock)、close(id, clock, reason)、sla(id, clock) 和 queue()。去重键是 cve、package、version 三元组，cve 转大写；版本按数字段比较；严重度取 CVSS，KEV 只在 kev_until 未过期时提为 critical；SLA 天数为 critical 7、high 14、medium 30、low 90，不可达加 30 天，只算周一到周五并排除 holidays 列表；例外必须由非申请人批准，带 expires_at，批准后 due 延长到 expires_at，过期恢复原 SLA；单个负责人未关闭超过 20 条拒绝派单；关闭后同键再次 ingest 要重开并记一次 reopen；未知严重度、负 CVSS、空 cve、过期例外都报错；queue 给各级计数、逾期数、待审批例外数。十五条用例眼下全红。

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
