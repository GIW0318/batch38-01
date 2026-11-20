# GSB Bugfix Task
## 题面
堡垒机查 authorized_keys，KeyAudit 按空格硬切：command=... 里的空格把选项当密钥类型，注释里的逗号当选项分隔，from= 地址列表不校验，expiry-time 不识别 YYYYMMDD，RSA 1024 也过，同公钥换注释算两条，撤销指纹不比对，cert-authority 被忽略，base64 夹换行也能解析，空行和纯注释直接崩，单用户 key 数没上限。ssh_keys_audit.py 的 KeyAudit 负责 parse(text)、audit(policy, now) 和 findings()。选项按逗号切，值支持双引号转义；command、from、expiry-time、permitopen、no-pty、cert-authority 都识别，重复选项冲突报错；类型只允许 ssh-ed25519、ssh-rsa、ecdsa-sha2-nistp256；指纹是 SHA-256(blob)；RSA 位数从模数算，低于 min_rsa_bits 记问题；同指纹跨用户记 duplicate；过期按日期整数比；超 max_keys_per_user 记问题；parse 坏行跳过计数；findings 按严重度排序。十五条断言全红。

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
