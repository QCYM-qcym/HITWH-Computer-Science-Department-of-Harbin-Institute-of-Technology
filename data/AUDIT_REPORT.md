# UGR16v3 首轮真实载荷审计

日期：2026-10-21。代码依赖基点：`74f163bf69559f02ad70ae1d5bb730e1f10d15bf`。身份：真实数据审计，**Data Gate 未通过，未运行真实模型**。

来源为[提供方仓库](https://github.com/josecamachop/UGR16_FeatureData/tree/760863d31413739a129b3be2d1d52cde217962e8)，固定提交 `760863d31413739a129b3be2d1d52cde217962e8`。只下载 UGR16v3.mat 和该版本四份 CSV，载荷总计约56 MB，均在忽略目录 .runtime/w1/raw；不再分发。仓库 LICENSE 为 GPL-3.0，既有论文数据声明另有 CC-BY-NC；使用条件仍需综合核验，不把仓库许可证等同于数据无条件再分发授权。

| 项目 | 作者训练范围 | 作者测试范围 |
|---|---:|---:|
| 行数 | 72,644 | 27,697 |
| 特征/标签宽度 | 134 / 8 | 134 / 8 |
| 首个本地时钟 | 2016-03-19 00:00 | 2016-07-28 00:46 |
| 最后本地时钟 | 2016-05-31 23:59 | 2016-08-26 23:59 |
| 间断次数 | 850 | 1,354 |
| 首尾之间缺少的分钟 | 33,916 | 15,457 |
| 重复 / 逆序 | 0 / 0 | 0 / 0 |
| 非有限或负计数行 | 0 | 0 |
| 八标签全零正常候选 | 2,874 | **0** |
| 四类主要攻击分钟 | 0 | 932 |
| 仅背景标签分钟 | 69,770 | 26,765 |

四份 CSV 均逐值等于对应 MAT 矩阵，字段顺序一致；CSV 首列 Row 为分钟时间字符串，逐行等于 MAT 的 obs_l/obs_lt。首列不属于模型134维输入。八标签顺序符合公共契约，攻击与背景重叠仍计攻击。[提供方 README](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/README.md)的测试43,200行描述与本次 v3 实际载荷不同，不能用说明中的数量替代载荷审计。

训练正常候选仅出现在本地时钟2016-05-30 00:06至05-31 23:59，连续2,874分钟。四段尚未划定；在未切分的整段上，H=15/30时分别只有2,859/2,844个当前及历史均正常的候选。这些数量不是训练/校准已可用的证据。测试没有正常候选，目标误报率及正常高负载误报率的分母为零。

## 失败原因和后续决定

- `obs_l/obs_lt` 和 Row 都未携带时区。没有来源证明，不能默认西班牙时区、UTC或本机时区；四个 UTC 区间未冻结。
- 冻结标签政策下测试正常候选为零，无法验证课题主要误报目标。不能把背景分钟改成正常、删除背景列或移动测试范围来绕过此问题。
- 正常候选集中在作者训练范围末尾，模型训练、验证和独立校准的样本供应尚未验证；许可条件与高负载计数口径仍待核验。
- 需 W0 汇总上述证据后决定后续数据核验或研究协议调整。当前未修改公共契约、未更换数据版本、未恢复均值差值方案。

当前 pipeline 明确拒绝 `REAL_DATA` 注册项；没有可以凭布尔标志绕过的真实训练入口。真实 IF、当前 AE、历史增强 AE、窗口选择、三种子实验、容量匹配及正式比较全部 **NOT_RUN**。仅合成数据可执行模型检查。

## 文件校验

| 文件 | SHA256 |
|---|---|
| UGR16v3.mat | eaf3fc4f56b3d79daeb015a2991f3bf4c80490e102ae9780f69811955de50d0d |
| UGR16v3.Xtrain.csv | ee6b36d2253971d6e110797bec81a7eb8ec3db290be5bd80974a7c76c69a5f3d |
| UGR16v3.Ytrain.csv | d75c433261be9fed5f65a8f98e72cadf8b56c2f9738608cd59706bed2ba463ed |
| UGR16v3.Xtest.csv | af052c8c3aff5bf20adb4f38a4b088c1b5e369aab39e923bd0106cb64ae28dde |
| UGR16v3.Ytest.csv | adc191e35b4d6a48ef83f68520387b94b01baad326cc9b9214136fae7435c159 |

下载时将 URL 固定到上述提供方提交，文件保留原名；不从 main 浮动版本复跑。准备载荷后，在本工作区运行：

```powershell
.venv\Scripts\python -m traffic_anomaly.cli audit-provider --mat .runtime/w1/raw/UGR16v3.mat --csv-root .runtime/w1/raw --report .runtime/w1/outputs/w1-audit/report.json
```

预期返回码2，表示 Data Gate 未通过；完整 JSON 保存在本地。此命令实际执行，结果不是计划或模拟值。规范 CSV 审计另用 `audit --source <CSV> --schema <DatasetSchema JSON> --report <本地JSON>`。

## 2026-10-21 W0阻塞复核增量

本轮重新运行provider-audit-v2，对五文件逐值/时间轴和官方Git blob复核，计数及SHA256与上表一致；structure_trusted=true仅指结构，gate_passed=false、退出码2。新增未知标签、逐标签/重叠、未匹配和四段NOT_DEFINED/null审计。未运行真实模型。详见[标签核查](../docs/research/2026-10-21-data-gate-label-audit.md)、[时间证据](../docs/research/2026-10-21-data-gate-time-semantics.md)、[许可对照](../docs/research/2026-10-21-data-gate-source-license.md)与[统一Gate决定](../docs/project/DATA-GATE-2026-10-21.md)。

旧提供方审计对损坏标签和错序缺少保护，本轮最小失败测试后修复；原始真实载荷没有触发，修复前后分类无差异。classM辅助字段实为HHMM编码，不能用来作分钟差。UTC、许可关系、三开发段和正式FPR目标继续阻塞。
