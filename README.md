# GSB Bugfix Task
## 题面
制作系统接批量单后，材料扣了东西没出：替代材料没降品质，暴击判定用时间种子，批次里一件失败其他件已经扣料，分解返还的材料和实际投入对不上，同一 seed 两次结果不同。crafting_quality.py 的 CraftBench 负责 craft_batch(recipe_id, slots, seed, stamp)、quote(recipe_id, slots)、salvage(item_id, stamp) 和 ledger()。recipe 有基础品质、材料组和替代表；每个组必须满足数量，替代材料按 0.8 计入品质；总分是材料品质均值 30%、工匠技能 10%、seed 确定性 roll 0 到 20；roll 到 20 暴击产出双份；批次要么全部成功要么全部回滚，不能只扣一半料；物品 id 由 recipe、slot、seed 派生且唯一；salvage 只接受本批次产出的物品，按原始材料组返还一半向下取整，替代料按替代关系返还，绑定物品拒绝；quote 返回材料缺口和预计品质区间；缺料、多料、未知配方、负种子、重复物品 id 一律拒绝；manifest 给批次、消耗、产出和 salvage 汇总。十五条用例全红。

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
