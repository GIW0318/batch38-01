# GSB Bugfix Task
## 题面
仓库改成分页后，玩家整理背包开始丢东西：两个半组材料不合并，先找空格再回头填旧堆；锁定格被整理挪走；超过单格上限直接截断；绑定物品和普通物品混堆；整理后顺序每次不同；取出数量大于实际也能扣；同一格重复 item id 不合并；分页 0 到 5 越界不报错；detail 透出内部数据列表。bank_tab_sort.py 的 VaultSort 负责 deposit(tab, item, count)、withdraw(tab, item, count)、compact(tab) 和 detail()。每页 30 格，item 带 id、stack、bound 三个字段；deposit 先填同类未满堆，再占空格，放不下整笔拒绝，不能留半笔；withdraw 数量必须是正整数且不超过可用数量；compact 跳过锁定格，按 category 再按 item_id 稳定排序，同 id 合并到上限；绑定物品只能和同绑定状态合并；tab 只允许 0 到 5；未知 item、负数数量、超容量按非法输入处理；detail 返回每页的格子快照和总件数。仓库自带十五条检查全红，测试文件不许动。

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
