# GSB Bugfix Task
## 题面
CSP 报告把安全运营淹了：report-uri 和 report-to 两种格式只认一种，blocked-uri 带随机 query 去重失效，刷新几次就重复上报，外部伪造 document-uri 也计数，单条几百 KB 也收，未来时间戳也收，directive 两种写法没合并，采样率写死 1，每个来源没配额，空报告崩，一条坏记录丢整批。csp_report_ingest.py 的 CspReportSink 负责 ingest(reports, now)、summary(top=5) 和 violations()。两种格式都接，必备 document-uri、blocked-uri、一个 directive；document-uri 取小写主机去默认端口，blocked-uri 除 self、inline、eval、data 外只留主机；去重键是文档主机、directive、blocked 主机；每个文档主机每小时 100 条，超出记 dropped；单条上限 8KB；早于 now-86400 或晚于 now+300 丢弃；未知字段忽略，缺字段跳过计数；summary 按次数降序、键升序；violations 给 received、dropped、unique。十五条断言全红。

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
