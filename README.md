# GSB Bugfix Task
## 题面
密钥托管要从整份备份改成门限共享，安全评审拿旧实现做了几组实验，结论是不能上线：固定系数导致任意两份份额就能还原；threshold 大于 shares 也接受；shares 超过 255 不报错；x 重复时后一份静默覆盖前一份；份额没有校验位，改一个字符 combine 出来是垃圾；combine 对传入顺序敏感；少于 threshold 时返回截断的秘密而不是拒绝；秘密长度没有上下限；空秘密直接崩；seed 不同结果不可复现；份额字符串大小写混用。shamir_split.py 的 SecretSharer 负责 split(secret, threshold, shares, seed)、combine(shares)、verify(share) 和 dump()。系数用 seed 派生，GF(256) 上运算；threshold 至少 2 且不超过 shares，shares 最多 255；份额格式 x.y，y 是十六进制并带四位 CRC32 校验；x 重复、格式错、长度不一致、校验失败都抛异常；combine 接受任意顺序、多余份额可以用、少于 threshold 拒绝；还原结果必须和原文逐字节相同；verify 只返回布尔值不抛异常；dump 只暴露 threshold、shares 和已发出的 x，不出现秘密或系数。仓库那十五条用例一条也过不了，断言别改。

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
