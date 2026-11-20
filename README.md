# GSB Bugfix Task
## 题面
单点退出改成票据中继后，运维发现退出风暴和状态错乱：一个退出请求给 20 个 SP 各发一张票，某张票超时重试后被 SP 当成两次退出，审计里出现两条；票没有绑定 SP，A 的票能投到 B 的回调；中继节点重启后旧票在新节点验不过，用户被卡在半退出；某个 SP 一直超时，调度器无限重试，把后面的 SP 全堵住；三个 SP 成功、两个失败，会话状态却写成 success；旧票晚到把已经成功的状态覆盖成失败；票据过期后仍在投递；回调响应里的随机串不校验，伪造的成功也记账；同一 SP 重复发起退出没有合并，票据数量暴涨；state 返回内部字典。slo_ticket_relay.py 的 SloRelay 负责 plan(session, idp, sps, now)、dispatch(ticket, now)、ack(ticket, sp, nonce, now) 和 state(session)。plan 按 SP 去重后每 SP 一张票，票是 32 位十六进制并绑定 session、idp、sp，120 秒有效，最多 20 个 SP；dispatch 只能投给票绑定的 SP，每次尝试计数，最多 3 次，过期拒绝；ack 校验 nonce 单次有效、SP 匹配、票未过期，重复 ack 幂等；state 按实际 ack 聚合，全成功 success，有失败且还有重试 partial，重试耗尽 failed，旧票的 ack 不能覆盖新状态；空 session、未知 SP、超时票据都报错；state 和返回的票都是副本。十五条用例全红。

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
