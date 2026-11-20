# GSB Bugfix Task
## 题面
日志平台接了一个模板字段，上线第二天 SOC 就收到 JNDI 外联告警。LookupShield 现在只会做字符串替换：${${lower:j}ndi:ldap://...} 这种嵌套能直接过；默认值 ${x:-${jndi:...}} 会被二次展开；递归没有深度上限，循环引用把栈打爆；未知变量原样输出，攻击者用它探测上下文；$${ 转义失效；env. 前缀没有白名单，能读任意环境变量；sys: 能取到进程属性；输出长度没有上限；大小写和 URL 编码的协议名绕过黑名单；控制字符原样进日志。lookup_expansion_guard.py 的 LookupShield 负责 render(template, context, policy)、scan(value) 和 dump()。只支持 ${name} 和 ${name:-default} 两种形式；name 必须命中 app.、env.、ctx. 三个前缀之一；解析出来的 key 里出现 jndi、ldap、rmi、dns、http、file 任一协议名就拒绝，大小写和百分号编码先归一；嵌套展开深度最多 5，循环引用直接拒绝；default 允许再含 lookup 但计入深度；$${ 输出字面量 ${；未知 key 保留原文；替换进去的值不再二次展开；输出超过 4096 字符、花括号不配对、空 name 都直接拒绝；scan 返回命中的模式和位置列表；dump给出渲染次数和拒绝次数。十五条用例一条也过不了。

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
