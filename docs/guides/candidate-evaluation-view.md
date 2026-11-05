# 查看候选运行的完整测试评价

日期：2026-11-06。范围：已保存人工运行的 `SYNTHETIC_ONLY / AUDIT_ONLY` 结果。实施依据见[本轮计划](../superpowers/plans/2026-11-06-autonomous-development.md)。本页说明如何读取同一运行的完整测试评价；实际验证范围随本轮证据更新。

## 命令与接口

在已经安装核心和后端包的环境中，使用同一套 records、inputs 和人工运行包：

```text
python -m traffic_anomaly.candidate_view_cli --records <records-directory> --inputs <inputs-directory> --source-fixture <synthetic-fixture> --if-run <saved-if-directory> evaluation
```

AE 使用 `--ae-run`，不能同时提供两种运行参数。`evaluation` 不接受时间、页码或政策过滤；成功输出完整JSON，失败输出安全错误码。省略source时，运行来源核查状态仍是 `NOT_PROVIDED`。

用[候选启动命令](candidate-viewer-launcher.md)打开同一运行包后，`GET /candidate/v1/runs/{run_id}/evaluation` 返回相同视图。该接口不接受查询参数。所有登记运行先通过评价形状检查，再启动服务；不会提供一个只加载了部分有效包的目录。

## 如何理解页面数字

“完整保存评价 · 测试分钟”展示三种标签映射各自的分钟人口、TP/FP/TN/FN及precision、recall、F1、FPR、FNR。三政策对应同一组已保存预测，是审计对照，尚不是正式标签决定。

- 测试日历分钟 = 可评分测试分钟 + 排除的不可评分测试分钟。
- 可评分测试分钟 = 正常候选分钟 + 攻击分钟 + 未知分钟。
- FPR的分母是可评分正常候选；recall和FNR的分母是可评分攻击。
- precision的分母是正常候选与攻击分钟中的报警数。UNKNOWN和不可评分分钟不计入混淆矩阵。
- 分母为零显示“不可计算”及保存的原因；数值0保持0。没有提供高完成流子组结果时，不生成对应指标。

现有四个人工包的全轴为144分钟，其中全轴可评分24分钟；完整测试段是36分钟，只有6分钟可评分、30分钟排除。这三组范围不同。曲线分页、时间范围和空页面仅影响显示记录，不能改变完整测试评价。

## 值与文件的关系

视图消费安全加载器已经核对的 `report.policies`，返回独立副本。`evaluation_reference` 给出原评价文件的SHA-256及字节数；视图不是原文件逐字节导出。`FULL_STORED_RUN` 表示文件属于哪个运行，`FULL_STORED_TEST_EVALUATION` 表示当前指标覆盖该运行的完整规定测试段。

加载阶段仍会检查保存的变换、历史、阈值和评价关系；查询阶段不重新计算这些内容，不训练或评分。`run_source_replay` 只表示运行侧原有核查，不能替代输入与运行配对的combined来源状态。

评价区域有独立错误与重试状态。切换运行或重载目录会清空旧评价，晚到响应不能覆盖新运行；曲线过滤不重新请求评价。页面保留空值原因和文件摘要，便于核对原结果。

本功能不改变生产134/268维契约，不启动真实数据链路，不比较分数尺度或推荐模型。Data Gate及真实研究阶段按[统一记录](../project/DATA-GATE-2026-10-21.md)判定。

实际验证：全量Python1611项及56子测试、前端102项通过，两个符号链接权限测试跳过。四旧包CLI/HTTP和安装后的页面逐值核对通过；独立审查修复了摘要数组被正则转换接受的问题。测试准备中的人工模型运行与实际只读验收分开记录，见[完整证据](../research/2026-11-06-candidate-evaluation-view-verification.json)。
