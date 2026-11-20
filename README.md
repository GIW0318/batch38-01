# GSB Bugfix Task
## 题面
团本换套装后，装备耐久和修理报价对不上：同一件紫装白装磨损速度一样，死亡一次只扣固定点，环境伤害不扣耐久；祝福在第一次归零时挡了一下，第二天又被当成新的祝福；升级最大耐久后当前值按绝对值保留，套装中一件碎了套装效果还亮着；修理商报价可以被复制，报价期间装备又挨打仍按旧价结算；两个窗口同时拿同一张报价单都能修成功；战斗中也能修理和升级；审计里只记了最终耐久。durability_wear.py 的 DurabilityBook 负责 wear(item_id, hits, cause, t)、quote(item_id, points, t)、repair(item_id, quote_id, t)、upgrade_max(item_id, new_max, t)、set_combat(flag)、reconcile() 和 audit()。quality 1 到 5 的磨损系数是 1.0、0.9、0.8、0.7、0.6，按 hits 乘系数向上取整；cause 为 death 额外扣最大值 10%，environment 只扣一半；current 到 0 进入 broken，属性按 0；祝福每件每天只能挡一次，归零时保留 1 点；套装四件中任一件 broken，整套加成为 0，reconcile 返回各套装生效件数；quote 生成 32 位十六进制报价单，锁定当前缺失点数和单价，60 秒过期且只能消费一次，期间装备耐久变化则报价作废；repair 不能在战斗状态、不能超过缺失点数，费用按报价单；upgrade_max 按原百分比换算当前值并让未使用报价单失效；未知物品、负数、过期或重复报价单、越权操作都拒绝；audit 按序号记录每次磨损、报价、修理、升级，返回。十五条断言全红。

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
