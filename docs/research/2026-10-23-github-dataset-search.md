# GitHub 数据来源核查：CICIDS2017 流表

- 核验日期：2026-10-23（Asia/Shanghai）。
- 目的：寻找可保留时间、持续时间、协议、包数、字节数及标签的 CICIDS2017 流表来源，为因果分钟聚合提供候选；本轮只核查仓库说明、Git 树和文件元信息。
- 范围：三个 GitHub 仓库的镜像核查，另追踪其中一个仓库公开列出的 Hugging Face 镜像元信息，并整合并行核查任务的作者修订版证据。
- 执行边界：未提交官方表单，未获取 ZIP、CSV、PCAP 数据载荷，未在线解压或查看包内内容；未改变主数据、表示、生产契约或 Data Gate。

## 结论

GitHub 能提供数据获取线索，但本轮核查的三个仓库没有直接托管可采用的原始流表。最有用的线索是 `zhadyz/AI_SOC` 指向的 Hugging Face `bencorn/CICIDS2017`：平台元信息已列出名为 `csvs/GeneratedLabelledFlows.zip` 的实际大文件对象、确切字节数和 LFS SHA-256。它是第三方镜像候选，不是已认证的官方发行物，也尚未完成本项目载荷审计。

## GitHub 仓库核查

| 仓库及固定快照 | 实际托管内容与身份 | 文件大小及校验的证据边界 | 本项目判断 |
| --- | --- | --- | --- |
| [rokibulroni/CIC-IDS-2017-Dataset](https://github.com/rokibulroni/CIC-IDS-2017-Dataset/tree/f2ec6ceca5be291ae607931423568d23e22b393c) | 完整 Git 树 `truncated=false`，只有 `README.md`、`CSVs/readme.md`、`PCAPs/readme.md` 三个文档；没有 ZIP、CSV 或 LFS 指针数据文件 | README 将 `GeneratedLabelledFlows.zip` 写为 `271 MB`，目标和 `.md5` 均为旧官方 IP 的外链；未给出完整 MD5 值。本轮不追踪下载链接，不将这段第三方说明视为当前官方文件大小或校验 | 仅链接索引，不能称为 GitHub 数据镜像。README 中“钓鱼”相关概述与数据身份没有建立充分对应，不据此推断适用性 |
| [zhadyz/AI_SOC](https://github.com/zhadyz/AI_SOC/tree/bfa03a36c28e89c1992606ec03f1abb0184c4505) | 完整 Git 树 `truncated=false`；`datasets/CICIDS2017/raw` 只含来源 README。说明大包及 CSV 排除在 Git 外，并明确镜像不属于 UNB 官方端点 | 来源 README 给出 HF 镜像链接及 SHA-256；仓库还说明旧 `.md5` 实际为 HTML 404，已移除。它提供校验线索，不能替代本项目审计或官方证明 | 有价值的来源线索，实际数据对象在 HF，不在 GitHub |
| [ctinnil/CY0P5_ML_Datasets](https://github.com/ctinnil/CY0P5_ML_Datasets/tree/470758e2b4c3c5f6226a6d3d793ae8630cf41b7c) | 完整 Git 树 `truncated=false`；含 notebook、脚本和结果文件，无原始 `TrafficLabelling` CSV 或目标 ZIP | [字段差异脚本](https://github.com/ctinnil/CY0P5_ML_Datasets/blob/470758e2b4c3c5f6226a6d3d793ae8630cf41b7c/helper_scripts/find_diff_features.sh) 的注释声称其比较的 `TrafficLabelling` 比 `MachineLearningCVE` 多 `Flow ID`、源/目的 IP、源端口、`Protocol`、`Timestamp`；没有本轮目标包对应的载荷或校验 | 可作为两类 CSV 不可互换的辅助线索；不能证明当前候选包字段、时间精度和正常样本供应 |

Git 树证据：

- [rokibulroni 固定 Git 树](https://api.github.com/repos/rokibulroni/CIC-IDS-2017-Dataset/git/trees/f2ec6ceca5be291ae607931423568d23e22b393c?recursive=1)。
- [zhadyz 固定 Git 树](https://api.github.com/repos/zhadyz/AI_SOC/git/trees/bfa03a36c28e89c1992606ec03f1abb0184c4505?recursive=1)；[来源说明](https://github.com/zhadyz/AI_SOC/blob/bfa03a36c28e89c1992606ec03f1abb0184c4505/datasets/CICIDS2017/raw/README.md)。
- [ctinnil 固定 Git 树](https://api.github.com/repos/ctinnil/CY0P5_ML_Datasets/git/trees/470758e2b4c3c5f6226a6d3d793ae8630cf41b7c?recursive=1)。

以上“无原始文件”均仅针对所列快照的完整 Git 树，不扩大为其历史提交、Release、外部存储或整个 GitHub 均无文件的结论。

## 由 GitHub 追踪到的 HF 候选对象

来源：[HF 文件列表元信息 API](https://huggingface.co/api/datasets/bencorn/CICIDS2017/tree/main/csvs?expand=false)，由本轮主核查任务读取平台元信息；未读取 ZIP 载荷。[仓库元信息 API](https://huggingface.co/api/datasets/bencorn/CICIDS2017) 返回提交 `811c007f08d693a8a8b4226c197c138391806ce6`，`private=false`、`gated=false`、`disabled=false`，最后修改字段为 `2026-03-05T06:56:24Z`。这些字段说明平台查询时的托管状态，最后修改时间不作为官方数据版本号。

该提交的 [README](https://huggingface.co/datasets/bencorn/CICIDS2017/blob/811c007f08d693a8a8b4226c197c138391806ce6/README.md) 明确自称非官方镜像，并将 UNB 列为权威说明及条款来源；数据卡 `license=other` 不提供新的明确许可授权。

| 项目 | Generated 对象 | MachineLearning 对象（仅作身份区分） |
| --- | --- | --- |
| 路径 | `csvs/GeneratedLabelledFlows.zip` | `csvs/MachineLearningCSV.zip` |
| 平台列出的字节数 | `283876488` | `235102953` |
| Git blob OID | `1e2cb1a68a00323f6798fe0bdceb57a24e2af5f6` | 本记录未列出 |
| LFS SHA-256 | `7bdbef286f8893f31c6db12105fa097fa5c2dcc6733179037a08129d150ea27a` | 与 Generated 对象不同，本记录未列出 |
| 固定提交浏览入口 | [Generated 对象页](https://huggingface.co/datasets/bencorn/CICIDS2017/blob/811c007f08d693a8a8b4226c197c138391806ce6/csvs/GeneratedLabelledFlows.zip) | [MachineLearning 对象页](https://huggingface.co/datasets/bencorn/CICIDS2017/blob/811c007f08d693a8a8b4226c197c138391806ce6/csvs/MachineLearningCSV.zip) |

HF 平台对它所托管对象提供的字节数和 LFS 哈希属于该镜像的对象身份信息。SHA-256 与 `AI_SOC` 公开说明一致，但不能标为 UNB 官方校验，也不能单凭文件名与哈希相符认定镜像未经修改或具有完整再分发授权。

仍未知或尚未验证：

- 与 UNB 官方发行物的逐字节对应关系和官方校验。
- 压缩包成员、解压后规模、实际字段及跨文件一致性。
- 时间戳格式、精度、单位、时区、DST 和流统计实际可获得时刻。
- 标签完整性、正常与攻击分钟供应、历史预热后有效分钟及四段可行性。
- 镜像数据及其标签的具体再分发许可适用关系。

## 作者修订版：独立备选

并行核查任务另找到 [GintsEngelen/CNS2022_Code](https://github.com/GintsEngelen/CNS2022_Code)，这是对应标注与实验代码的 GitHub 来源，数据载荷位于作者网站而非该仓库。主核查任务独立读取了[作者文件目录](https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/)及[工具文档](https://intrusion-detection.distrinet-research.be/CNS2022/Tools_Documentation.html)。

- 目录实际列出 `CICIDS2017_improved.zip`，显示修改时间 `2023-04-27 16:41`、大小 `328M`。这里保留目录原单位，不换算为确切字节，不将修改时间作为版本号。
- 目录还列出 2018 修订包，显示 `9.7G`，不作为当前优先获取对象。
- 工具文档说明修订内容包括 UTC 微秒时间表示和新增 ICMP 相关处理；这是修订流程的说明，不能套到原始 UNB `GeneratedLabelledFlows.zip`。
- [数据下载说明](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html)解释 `Attempted` 语义。若采用，必须重新决定标签映射及评价政策，不能冒充原始 CICIDS2017 发行物。

本轮没有下载修订 ZIP，也未认证其具体压缩成员、载荷、校验和本项目四段供应。该来源是有文档证据的独立备选；当前优先推进 HF 原包候选的来源核对及有界审计准备，未扩大或改变主数据选型。

## 对当前工作的含义

可以把 HF 对象作为有确切传输大小的候选，继续形成有界获取和审计方案；是否获取与采用，沿用已有授权和研究决定边界。本轮没有执行获取，不自动替换 C17-G12 的来源决定。

`MachineLearningCSV`、清洗后学习表或随机切分表不能仅凭 CICIDS2017 名称替代目标流表。因果分钟构造仍需要核实实际时间、持续时间及统计字段；不得补造时间戳、协议或补零凑旧维度。完整流统计不能回填到流开始分钟。

当前研究状态保持 S2，Data Gate 为 `BLOCKED`；真实解析、四段供应审计、训练和正式比较继续为 `NOT_RUN`。镜像元信息已知不等于载荷或研究评价通过。
