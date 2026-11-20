# GSB Bugfix Task
## 题面
证书吊销出了事故：基础 CRL 和增量 CRL 一起加载后，上周吊销的中间证书还能握手。crl_window.py 的 RevocationWindow 负责 load(base, delta, now)、check(serial, issuer, now) 和 window()。现在的问题：增量号对不上也合并；removeFromCRL 不删基础条目；序列号大小写和前导零当成两张证；nextUpdate 过了还信；thisUpdate 在未来也收；issuer 只比前缀；同号冲突取后一条；未知 critical 扩展不拒；增量比基础旧也套用；基础过期、增量新鲜就整体放行。要求：序列号转大写去前导零；增量仅在 base_number 相等且 this_update 不早于基础时生效；removeFromCRL 只撤基础表对应项；now 落在 this_update 与 next_update 之间才算有效，边界算有效；issuer 逐字相等；冲突、负数、空 issuer、未知 critical 扩展都拒绝。check 返回 revoked、reason、effective_at；window 给条目数和时间窗。十五条用例全红。

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
