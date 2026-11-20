# GSB Bugfix Task
## 题面
商人改动态库存后，价格和限购全乱：库存低于两成不涨价，高于八成不打折，每日限购跨天不重置，金币不够先扣库存，声望折扣按等级线性加，回购列表无限长，绑定物品也能卖。vendor_stock.py 的 VendorStock 负责 quote(player, item, count, ts)、buy(player, item, count, quote_id, ts)、sell(player, item, count, ts)、restock(ts)、buyback(player, index, ts) 和 shelves()。item 有 id、stock、base_price、daily_limit、bound；quote 锁定 30 秒价格和库存，返回 quote_id，同一 quote 只能消费一次，库存或价格变化则作废；buy 同时校验库存、金币、每日限购，任一不足整笔拒绝；限购按服务器 05:00 重置；声望 0 到 5 级折扣 0%、2%、5%、8%、12%、15%；动态价在库存低于 20% 时加 20%，高于 80% 时减 10%；sell 只收非绑定，价是当前价一半；回购保留最近 12 条、300 秒，价格锁定；restock 补满；负数、零数量、未知物品、绑定出售、过期 quote 都报错；shelves 给各物品库存、当日已售和回购数量。十五条用例全红。

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
