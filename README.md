# GSB Bugfix Task
## 题面
金库钥匙仪式改成多人会签后，审计发现单人可以绕过：同一操作员用两个身份重复批准，过期批准仍计入人数，批准只绑金库不绑动作，已撤销的钥匙还能解锁，两次解锁之间不需要重新会签，锁定后主管重置直接清空失败计数，审计只记了最后结果。vault_quorum_lock.py 的 VaultQuorum 负责 open_request(vault, action, operators, ttl, now)、approve(request_id, operator, credential, now)、unlock(request_id, credential, now)、deny(request_id, operator, now)、lockout(vault, now) 和 trail()。每个金库要求 3 把不同钥匙会签；operators 必须存在、未撤销且拥有 action 权限；请求 120 秒有效，单次批准 60 秒有效，批准只能用一次；批准必须绑定 request 和 action，不能跨金库复用；同一操作员重复批准只算一次并记冲突；unlock 时所有批准必须同时有效、请求未过期、钥匙未撤销，否则整体拒绝；连续 5 次失败解锁锁定 300 秒，锁定期间 open、approve、unlock 一律驳回；解锁成功后请求作废，下一次要重新会签；lockout 恢复必须两名主管在不同请求中批准，恢复清失败计数但不复活旧请求；未知金库或请求、空 operator、过期、重复、越权都拒绝；trail 按事件号记录请求、批准、拒绝、锁定、恢复，返回副本。十五条断言全红。

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
