# GSB Bugfix Task
## 题面
注册和改密共用一套强度条后，安全评审找出一串漏判：Password1! 满分，qqqqqqqq 满分，qwerty123 算强，p@ssw0rd 还原后仍高分，用户邮箱前缀直接通过，泄露库里的密码也给 4 分；改密时新密码只差一个字符也放行；反馈接口还能被刷。password_strength_meter.py 的 StrengthMeter 负责 score(password, user_inputs, breach_hashes)、feedback(password, user_inputs, breach_hashes)、check_rotation(old, new) 和 report()。先做 NFKC，长度按码点；基础熵按字符池，连续重复三次、abc/123/qwerty/azerty 序列、常见词表、l33t 还原、1900 到 2099 年份、user_inputs 子串都要扣分；breach_hashes 命中直接把分数压到 0；分数 0 到 4，阈值 20、36、60、80 bit；check_rotation 要求新旧至少 4 个位置不同且新密码不包含旧密码，否则拒绝；空串、纯空白、None 报错；feedback 返回固定顺序代码，最多五条，同一输入两次一致；report 记录评估次数、拒绝次数和最近分数，不存明文。十五条断言全红。

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
