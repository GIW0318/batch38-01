# GSB Bugfix Task
## 题面
主机审计规则换人维护后，关键目录漏审：watch 路径带空格被截断；-k 标签含逗号被拆成两条；同一规则重复加载不去重；-F arch 写成 b64 不认；syscall 列表里混入未知系统调用仍接受；规则顺序被打乱导致 exit 永远不触发；-p 权限位写 rwxa 之外也收；排除规则没有优先级；规则文件带注释和续行符解析错；空规则静默跳过；状态返回内部规则表。auditd_rule_parse.py 的 RuleBook 负责 load(text)、match(event)、snapshot()。watch 路径支持引号；标签只允许字母数字下划线；同一 watch 加 syscall 加 key 视为重复；arch 只允许 b64、b32；syscall 必须在允许表；-p 只允许 r、w、x、a 的组合；规则按文件顺序保存，exit 规则必须排在 watch 之后；排除规则以减号开头且优先；注释和反斜杠续行要处理；空规则报错；match 返回命中的 key 列表；snapshot 给规则数、重复数、未知 syscall 数。十五条用例全红。

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
