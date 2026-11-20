# GSB Bugfix Task
## 题面
车机互联的设备授权最近被安全评审打回：同一块车机屏幕先申请只读权限，确认后又把写权限带进凭据；短码在两家经销商后台同时被确认，两边都返回成功，先确认的账号反而拿到后确认者的授权；设备指纹在确认后被改掉，兑换接口仍然放行；账号改密或远程撤销后，之前没兑换的授权还能继续换凭据；同一个兑换句柄连点两次会发两枚凭据；未知句柄和已撤销句柄返回的错误文案不一样，能用来枚举；每台设备挂起的授权没有上限，短码可以被慢慢试；快照返回的是内部表的引用。device_code_grant.py 的 DeviceGrant 负责 begin(app_key, fingerprint, perms, now)、claim(short_code, account, now)、redeem(handle, fingerprint, now)、revoke_subject(account, now) 和 snapshot()。begin 只接受白名单接入方，perms 去重后不能为空且全部落在白名单，fingerprint 不能为空，句柄 32 位十六进制，短码是 6 位数字，有效期 300 秒；claim 去空格、全角数字转半角后只成功一次，绑定账号，并发只有一个赢家；redeem 要求已确认、指纹逐字相等、未过期且只兑换一次，发出的权限必须等于 begin 时的集合，不能追加；revoke_subject 让该账号所有未兑换句柄立即失效；每指纹最多 3 个未兑换；未知、过期、重复、指纹不符统一按无效授权拒绝；snapshot 给 pending、claimed、redeemed、revoked 计数。十五条断言全红。

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
