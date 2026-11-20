# GSB Bugfix Task
## 题面
多流顶点布局接进新管线后模型花屏：属性偏移没按 4 字节对齐，显式 offset 重叠也收，stride 不是 4 的倍数，属性超过 16 个不报，同名语义跨流重复，缺 position 也 build，整数格式开 normalized 但 float 也接受，shader 输入签名和布局对不上也放行，打包顶点时默认值丢失。vertex_stream_plan.py 的 VertexPlan 负责 add_stream(stream_id, attributes)、build(shader_inputs, max_streams=4, stride_hint=None)、pack(vertices)、layout()。最多 4 个流，流内属性格式 float32、float16、uint8、uint16、int16；每个属性按大小向上对齐 4 字节，显式 offset 不与已有区间重叠；stride 4 的倍数且不小于最后属性结束位置；总属性最多 16 个；语义名跨流唯一；build 前必须有 position；normalized 只允许整数格式；shader_inputs 的 name 和类型必须匹配布局，缺输入补默认值，多余属性拒绝；pack 按布局把字典顶点写成字节，缺字段用默认，越界拒绝；布局哈希稳定；未知格式、重复语义、重叠、缺 position、非法 stride、签名不符都报错；layout 给流数、属性数、字节数和哈希副本。十五条用例全红。

## 运行方式
```bash
python -m pytest tests -q
```

## 平台字段

所属领域：安全
子方向：图形渲染
任务类型：Bugfix
语言 / 框架：Python 3, pytest
环境可复现等级：有外部依赖，未容器化
