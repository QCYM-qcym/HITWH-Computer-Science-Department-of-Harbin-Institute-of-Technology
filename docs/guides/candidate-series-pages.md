# 候选分数曲线范围查询

日期：2026-10-31。状态：SYNTHETIC_ONLY。用途：按时间和页读取[运行快照](candidate-run-snapshots.md)中的既有分钟分数。依据[本批计划](../superpowers/plans/2026-10-31-candidate-series-page.md)。原始特征、历史偏离向量和独立标签仍通过[单分钟详情](candidate-minute-details.md)读取；本批不增加生产HTTP或网页接口。

```python
from traffic_anomaly.candidate_series import candidate_series_page

page = candidate_series_page(
    run_snapshot,
    start="2026-01-01T00:00", end="2026-01-01T00:32",
    page=1, page_size=20,
)
```

`run_snapshot`须由既有IF或AE候选加载器返回。查询本身不加载产物，不运行模型，不重新计算历史、校准或评价。调用时先核对完整分钟轴及分数有效性，再过滤和分页；完整轴外的无结果不能被补成正常分数。

start和end可以为None，分别表示开放边界；有值时仅接受无偏移整分钟的 `YYYY-MM-DDTHH:MM`、`:00`、`:00.000000` 形式，返回规范时间。范围为左闭右开 `[start,end)`；相等或逆序拒绝，有序但未匹配记录的范围返回空页。Z、时区偏移、24:00、非零秒、不在上述形式的小数或非法日期拒绝。时间基准保持 `synthetic_source_clock`，不转换成本地时区或认证UTC。

page是从1开始的整数，page_size是1至1000的整数、默认100。布尔值、字符串和浮点数不能代替整数。超出最后一页返回空items，total仍为该范围匹配数；空范围和超尾页保留同一运行的评价引用。无需匹配时间端点恰好存在于原轴，不插值或补齐采集缺口。

| 字段 | 含义 |
| --- | --- |
| range、page、page_size | 规范化范围和实际分页参数 |
| total / returned | 范围内全部原分钟数 / 本页返回行数，包含无效与预热分钟 |
| items.source_index | 原完整分钟轴上的索引，不是本页序号 |
| items.current_input_valid / valid | 当前输入可用性 / 原评分可用性，分别保留 |
| items.score、alarm、threshold | 保存的分数、报警和全局阈值；无效分数与报警保持null，全局阈值仍在 |
| items.history_invalid_reason | 原H15/H30原因，不能将历史不足显示成正常 |
| items.break_before | 原轴首行，或与原前驱跨分钟缺口、采集段、分区时为true；不是分页或范围边缘标记 |
| source_replay | 运行加载器的原来源重放状态，不表示单分钟接口的双快照配对证明 |
| evaluation_reference | 原evaluation.json的SHA/大小与run_id，scope为FULL_STORED_RUN；不提供服务器路径 |

范围匹配数与页面行数均不是误报/漏报分母。评价引用指向完整运行保存的规定评价人口，仍区分训练、验证、校准和测试及共同有效分钟，不表示对轴上全部分钟一起评价。指标与不可计算原因仍读取原报告；选择窄范围、空页或不同page_size均不重算、不更新指标。

break_before只表达显示所需的原时间/采集段/分区断开关系，不重建历史，也不证明采集完整。页首可能为false，原分区边界即使落在页中也为true。绘图时还须按null分数保留不可绘制点，不把无效分钟连成有效评分。

返回全新的普通字典与列表。修改items、range或评价引用不影响快照及后续查询。`CandidateSeriesError`公开code/消息使用 `INVALID_QUERY` 或 `INCOMPATIBLE_SNAPSHOT`，不带私人路径、载荷或堆栈。形状检查用于避免错读已加载值，不把对象当作来源认证或真实研究许可。

新增76项手写快照测试先失败后通过，无模型训练；相关164项通过，其中旧测试夹具仍含合成toy模型准备。主控实际四个旧人工包36次完整拼页、40次边界/别名、8次副本隔离、1次无源证明及26次错误参数检查通过，39文件SHA/大小/mtime保持。每包144行含120个无效分钟；旧包没有真实时间缺口，缺口逻辑由人工单元测试覆盖。私有验收脚本首次元数据属性名拼写错误已保留、修正并重跑通过，未修改候选源码。[实际记录](../research/2026-10-31-candidate-series-page-verification.json)。真实CSV、下载、真实训练评分校准和正式实验未执行；生产134/268契约保持，Data Gate仍BLOCKED。
