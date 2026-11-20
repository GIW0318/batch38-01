# GSB Bugfix Task
## 题面
商队跑长途后，利润和损耗对不上：路线封闭了还按原路走，护卫越多遇袭概率线性下降，生鲜超过两天不腐坏，提前到达也结算，保险理赔和保费没进账，改道后总时长不变。caravan_route.py 的 CaravanPlan 负责 plan(route, cargo, guards, insurance, seed)、depart(ts)、reroute(leg_index, new_path, ts)、arrive(ts)、claim(ts) 和 manifest()。route 每段有 distance、risk、closed；cargo 每项有 id、weight、value、perishable；总重不超 500；护卫每名把遇袭概率乘 0.9，最低 0.05，损失后士气下降再乘 1.1；遇袭按随机种子可复现地判定，损失该段货值 20%；生鲜超 48 小时每小时腐坏 5%；改道只能替换未走的段，增加 2 小时和 10% 运费；到达不早于总时长；保险保费是货值 5%，理赔覆盖损失 70%，同一次行程只能 claim 一次；利润等于售价减货值减护卫费减保费再减损耗加理赔；空货、超重、重复出发、提前到达、封闭段、负 seed 都报错；manifest 给总时长、各段损耗、利润和理赔。十五条用例全红。

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
