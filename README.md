# GSB Bugfix Task
## 题面
钱包接托管和退款后，金币和荣誉对不上：角色上限和账号上限只查一个，周上限周一零点重置，荣誉日上限没生效，超出部分蒸发，追赶加成没封顶，转账绕过周上限，托管解冻重复入账，退款超过原单，rollover 重复执行多给，对账发现差额但找不到流水。wallet_ledger.py 的 WalletLedger 负责 earn(player, currency, amount, now, source)、spend(player, currency, amount, now)、transfer(src, dst, currency, amount, now)、escrow(player, currency, amount, order_id, now)、settle(order_id, now)、refund(order_id, now)、rollover(now)、balance_check() 和 journal()。currency 只允许 gold、valor、honor；gold 有角色和账号上限，valor 周上限，honor 日上限；周和日上限 05:00 重置；超角色上限 50% 转邮件，超账号上限拒绝；追赶按错过周数乘 0.5 最多 3 倍；spend 不占周上限但不能为负；transfer 单日最多 10000 且双方都过上限；escrow 冻结资金，settle 只入账一次，refund 不超过原单且只能一次；rollover 同周幂等；balance_check 重算余额与流水，输出差额和最小差异单号；负数、零、未知货币、时间回拨报错；journal 按流水号记录。十五条断言全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：其他
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
