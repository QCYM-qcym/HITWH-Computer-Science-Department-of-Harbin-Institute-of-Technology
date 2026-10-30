# 攻击片段与逐分钟漏报的区别

日期：2026-10-30。状态：SYNTHETIC_ONLY 示例修正。依据：[原 W1 协议](../../experiments/PROTOCOL.md)、[公共契约](../design/contracts-v1.md)、[报告 V0.40](../reports/开题报告-V0.40-公开文本.md)。程序规则未改，真实研究 Data Gate 仍 BLOCKED。

## 修正依据

原 W1 提交 `2e85cd1` 的协议和评价测试已明确：混淆计数只使用有效分钟，完全没有有效报警的攻击片段按原始对齐标签轴划分。旧 W0 样例提交 `74f163b` 早于该实现，误将片段缩短到有效漏报分钟。本次修正这个示例，保留原分数、阈值、标签、有效性、覆盖和标量指标。

统一四分钟样例的攻击出现在 00:00、00:01，前一分钟处于历史预热；两分钟都没有有效报警。因此未报警攻击片段为 `[00:00,00:02)`，长度 2。有效攻击为 1，FN 为 1，被排除攻击为 1。正常分钟仍有一次误报、一次正确未报，FPR 仍为 0.5；这些手工值没有模型效果含义。

| 情况 | 既有行为 |
|---|---|
| 完整攻击段没有有效报警 | 列出整个标签片段，可能包含未评分分钟 |
| 整段都未评分 | 可列出片段，FN 为 0，攻击有效分母为 0、召回率 null；不能称该段已被评价为漏报 |
| 一段中仅部分有效分钟报警 | 不再列为完全未报警片段，其余有效未报警分钟仍为 FN，不作 point-adjust |
| 时间缺口或中间缺标签 | 中断片段；不填补分钟、不把缺标签当正常 |

现有 helper 先输出误报片段，再输出未报警攻击片段，分别按时间排列；样例序列已按其输出对齐，不新增跨类全局排序约定。现有片段接口没有采集分段字段，不能识别相邻时间戳之间未编码的采集重置。

## 页面与接口

页面改称“未报警攻击片段”，显示长度与 FN 的区别。点击样例片段定位至 00:00，保留“历史预热”、分数/阈值/报警未提供和 dos 事后标签；不自动跳过无效起点。页面只读原评价，筛选与分页不改变分母。

本次修正不增加后端 interval/high-load 验证；[现有后端核验](backend-evaluation-consistency.md)仍只覆盖六项汇总。历史保存包不自动更新，原始证据保留。生产 Pydantic 类型、OpenAPI Schema、生成 TypeScript 类型均未改；只由既有生成器同步 OpenAPI 中的区间示例。

另有独立待处理项：现有 FakeExecutor 将首条详情的通道复制到所有分钟，而网页 mock 按详情时间查找，缺项时通道为 null。此次未改该逻辑，不声称 API 与 mock 的所有解释通道相同。当前特征是否可用不能仅由评分有效性决定，后续应核查合成详情映射，不修改保存产物以掩盖差异。

## 实际验证

[机器可读记录](../research/2026-10-30-episode-example-verification.json)与[实施记录](../superpowers/plans/2026-10-30-episode-example-alignment.md)：

- 新增核心回归先得到 1 失败、4 通过；修正后相关 Python 98 项通过，含核心契约 21、既有评价 3、新增片段 5、后端 69。仅一项既有 TestClient 弃用警告。
- 前端先得到 3 失败、9 通过，再通过全套 25 项、typecheck、build 和 contracts:check。保留原构建包大小警告，未为消警扩大修改。
- 新建独立任务数据库和目录完成一次 FakeExecutor API 检查：原标签与无效评分状态保留，时间范围/分页不改评价，metrics、scores、config 导出与原保存字节完全一致；查询前后文件 SHA 与修改时间保持。模型库未导入，无训练、评分或校准。
- 独立 5187 端口实际打开 mock 页面，载入样例并定位到 00:00，确认片段 2 分钟、无有效报警说明、历史预热提示、dos 标签及缺通道“未提供”；页面检视后关闭临时服务，未覆盖既有端口或数据库。该浏览器检查与进程内 API 检查分别记录，未声称本批浏览器连接了 HTTP 后端。
- 独立 Spec/Quality 审查通过。未重复无关本地全套；真实 CSV、下载和真实模型执行均为 0，正式实验 NOT_RUN。

相关命令：

```text
python -X utf8 -m pytest tests/core/test_contracts.py tests/core/test_evaluation.py tests/core/test_fixture_evaluation.py tests/backend -q
python -X utf8 tools/contracts/export_openapi.py --check
npm run test -- --run
npm run typecheck
npm run build
npm run contracts:check
```

Python 使用项目虚拟环境，npm 命令在 `src/frontend` 执行。后续优先修复已定位的合成详情时间映射，再单独增加后端区间一致性核验；研究政策、主数据采用和真实试点仍需原有决定与 Gate 条件。
