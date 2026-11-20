# GSB Bugfix Task
## 题面
资产巡检扫出一批子域被第三方接管，CnameAudit 的实现却几乎没拦住：只跟一跳 CNAME，链尾指向已释放的云存储也发现不了；链里有环时直接死循环；名字大小写和结尾的点不同就当成两条记录；同一个名字有多条 CNAME 时只取第一条；apex 上的 CNAME 也照收；目标命中第三方指纹但后缀只是字符串包含就报警；通配符记录被当普通记录；TTL 为 0 不加风险；链尾 NXDOMAIN 不报；同名同时有 A 和 CNAME 也不报冲突；risk 排序不稳定；digest 把内部集合直接返回。dangling_cname_scan.py 的 CnameAudit 负责 scan(records, fingerprints, ts)、risk(host) 和 digest()。记录有 name、type、value、ttl、apex 五个字段；名字统一小写去尾点；链最多跟 8 跳，遇到重复就记 loop；apex 上的 CNAME、同名多 CNAME、CNAME 与 A/AAAA 并存都记 conflict；链尾没有 A/AAAA 且没有命中指纹记 dangling，基础分 60；指纹按标签边界做后缀匹配，命中加权重；通配符跳过；TTL 为 0 加 10 分；risk 按分数倒序、主机升序返回，分数相同不能每次不同；结构非法直接拒绝；digest 返回扫描数量和高风险主机快照。十五条用例一条也过不了。

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
