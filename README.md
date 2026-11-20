# GSB Bugfix Task
## 题面
游戏聊天一开跨服就失控：刷屏一分钟几百条，屏蔽词只做完全匹配，拼音和拆字绕过，私聊不受频率限制，被禁言还能在队伍频道发言，举报没有冷却，频道权限不校验，GM 消息也被过滤，审计视图会带出整张屏蔽表。chat_moderation.py 的 ChatGate 负责 send(player, channel, text, at)、mute(player, until, reason)、report(player, target, at) 和 gate_report()。频道只允许 say、party、guild、whisper、system；每条消息去空白、NFKC、转小写后再匹配屏蔽词；屏蔽词支持前缀树和中间插符；同一玩家 10 秒最多 5 条，私聊 10 秒 3 条；禁言期间所有玩家频道拒绝，system 除外；举报同一对玩家 60 秒一次；频道权限按玩家 guild/party 校验；GM 消息跳过过滤但仍记审计；空消息、超 500 字符、未知频道报错；gate_report 给发送数、拒绝数、禁言数。十五条用例眼下全红。

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
