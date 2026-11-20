# GSB Bugfix Task
## 题面
昵称仿冒：有人用西里尔 а 注册了和 admin 一样的号。HandleRegistry 只做 lower()：零宽字符绕过保留名，全角不做 NFKC，bidi 控制符反转显示，土耳其 I 处理错，保留名不看骨架，重名只比完全相等，长度按字节，组合字符和 emoji 被截断，0/O 与 1/l 没归一，resolve 不给规范名，空串和纯空白也过。confusable_handle.py 的 HandleRegistry 负责 register(name, now)、resolve(name) 和 handles()。先 NFKC 再 casefold，去零宽和格式字符，带 bidi 控制符直接拒；用表把西里尔、希腊、全角形近字母映射到拉丁骨架，0/O、1/l/I 归一；规范化后 3 到 24 码点，只允许小写字母、数字、下划线、点、连字符；保留名和已注册骨架冲突报错；resolve 已注册返回显示名、骨架、注册时间，未知返回 None；handles 给注册数与保留名。十五条用例全红。

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
