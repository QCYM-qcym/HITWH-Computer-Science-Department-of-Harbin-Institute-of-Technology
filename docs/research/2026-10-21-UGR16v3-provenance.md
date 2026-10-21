# UGR16v3 来源、标签与时间基准核验

核验日期：2026-10-21。状态：来源与标签证据核验完成，时区 UNVERIFIED；Data Gate 仍未通过。本轮只查阅提供方材料，并只读复核已取得的 v3 载荷；未下载其他版本载荷，未重标标签、修改协议或运行模型。

## 1. 核验对象与来源链

对象固定为提供方仓库提交 `760863d31413739a129b3be2d1d52cde217962e8` 下的 `matlab/UGR16v3.mat` 与四份同名 CSV；MAT 的 SHA256 为 `eaf3fc4f56b3d79daeb015a2991f3bf4c80490e102ae9780f69811955de50d0d`。这是 UGR’16 的派生分钟特征版本，不能与原始流记录、全部采集期或其他 v1/v2/v4 数据互换。[固定版本目录](https://github.com/josecamachop/UGR16_FeatureData/tree/760863d31413739a129b3be2d1d52cde217962e8)

原始数据来自西班牙 ISP 的 NetFlow v9 采集；原始 CALIBRATION 为2016年3—6月，TEST 为7—8月，后者混合真实背景与人工攻击。原始提供站按周组织数据。[原始提供方说明](https://nesg.ugr.es/nesg-ugr16/march.php)

特征提供方的数据管理计划把 F.3 定义为每个时间区间一行、134个计数特征、8类标签的全量特征表；F.2 则是每分钟144个计数器的中间格式。两种宽度对应不同处理阶段，不能据此把本次134维认定为缺列。其明确将前四类称为人工攻击，后四类称为原数据中观察并标注的真实活动。[ANIMaLICoS Data Management Plan，§2.1，PDF第3页](https://codas.ugr.es/animalicos/doc/deliverable3.pdf#page=3)

派生版本论文正式出版信息为：Camacho, J.; Rodríguez-Gómez, R. A. *Data Quality Tools to Enhance a Network Anomaly Detection Benchmark*. **Data**, 2025, 10(3):33，DOI `10.3390/data10030033`。固定 README 中的2024年工作题名应保留为上游历史，不作为正式出版元数据。v3 使用匿名化双向流，训练月份为3—5月；论文描述 nfdump → FCParser → 1分钟134维 FaaC 特征的处理链。[正式论文，§2.2、表2](https://www.mdpi.com/2306-5729/10/3/33)

固定提交的递归文件树只有 README、LICENSE、忽略规则和 CSV/MAT 数据，未附 v3 专用生成脚本、nfdump 命令、运行时区配置或删行清单。因此本轮不能重建每个缺失分钟的成因。[固定提交完整文件树](https://api.github.com/repos/josecamachop/UGR16_FeatureData/git/trees/760863d31413739a129b3be2d1d52cde217962e8?recursive=1)

## 2. 八列含义、顺序和值

固定 README 定义 Y/Yt 为每个观测的攻击计数；这不是单一类别编号或仅取0/1的标志。CSV 顺序与本地 MAT 的 `yvar_l` 一致：`dos, scan11, scan44, botnet, blacklist, udpscan, sshscan, spam`。[固定 README](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/README.md)、[Ytrain CSV](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/csv/UGR16v3.Ytrain.csv)、[Ytest CSV](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/csv/UGR16v3.Ytest.csv)

含义依据原始论文 §III-B、§IV-B 与表VII；数值范围和正值行数为本轮只读 CSV 全列计数，非论文给出的统计。原论文名与特征列名的对应由提供方分类说明、CSV 表头和本地 MAT 标签共同核对。[原始论文作者版本，表VII及标签说明](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)

| 列 | 原始论文标签及含义 | 训练：正值行数；值域 | 测试：正值行数；值域 |
|---|---|---:|---:|
| dos | dos；合并三种人工 DoS 变体 | 0；0 | 351；0—62,556 |
| scan11 | scan11；人工一对一扫描 | 0；0 | 76；0—24,036 |
| scan44 | scan44；人工四对四扫描 | 0；0 | 78；0—71,157 |
| botnet | nerisbotnet；混入受控环境 Neris 流量 | 0；0 | 448；0—41,737 |
| blacklist | blacklist；涉及公开黑名单 IP 的流 | 69,770；0—17,565 | 27,697；42—81,265 |
| udpscan | anomaly-udpscan；识别出的 UDP 扫描 | 0；0 | 0；0 |
| sshscan | anomaly-sshscan；识别出的 SSH 扫描 | 0；0 | 0；0 |
| spam | anomaly-spam；识别出的垃圾邮件活动 | 0；0 | 0；0 |

正值行数允许重叠，不可相加当作攻击分钟数。实际测试前四列正值的并集为932行；训练为0行。每个格子的值表示提供方计数，不代表该分钟发生了同数量的独立攻击事件。

`blacklist` 不是正常背景流量计数。原始论文明确提醒：涉及黑名单 IP 的流并不全都必然是攻击；原始 `background` 也是未证明为攻击的流，而非已证明干净的正常流。项目把后四列单列为“背景标签”，是评价协议的分组术语，应写清“真实背景中已标注的可疑/异常活动”。不能据“后四列非零”推导“可信正常”，也不能据“任意八列非零”统一称背景：前四列还包含已知人工攻击。[原始论文，§IV-B](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)

## 3. 时间基准与时区

| 层次 | 已核验事实 | 不应推导的结论 |
|---|---|---|
| 原始采集 | 原始完整采集时间见论文表1；与按周下载文件组织相对应 | 不能把采集首尾直接当作 v3 保留行首尾 |
| v3 时间字符串 | `Row`、`obs_l/obs_lt` 是12位 `YYYYMMDDHHmm`；本地首值如 `201603190000` | 不是 Unix epoch；未携带 UTC 偏移 |
| MAT 日内/日期辅助列 | 上游称日内分钟；本轮全量复核实为HHMM整数编码，详见新的时间证据；`classD/classDt` 为日期整数 | 辅助列不是独立时区证据 |
| 文件创建时间 | MAT header 记录2023-05-22创建，README 自述2023-05-26修改，Git提交时间另有 UTC 元数据 | 这些属于产物或文档时间，不是2016采集时区 |
| 数据源时区 | 已核验材料中未获得 v3 字符串对应的时区、夏令时规则或转换记录 | 不能默认 UTC、Europe/Madrid 或本机时区 |

本地时间格式与值来自已下载载荷只读检查；README 对辅助列的定义为 observation timestamp、minute in day、day timestamp、workday/weekend。[固定 README](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/README.md)

用于进一步核查的通用 FCParser 源码 `TimeVariable.load()` 调用 `datetime.strptime(raw_value, tsformat)`；其示例 netflow 配置使用不带时区的格式 `%Y-%m-%d %H:%M:%S`。该配置不是已证明用于本次 v3 的配置，既不能证明 v3 是 UTC，也不能证明其采用西班牙民用时间。[FCParser 源码，第210—237行](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/bin/faac.py#L210-L237)、[示例配置，第36—37行](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/example/config/netflow.yaml#L36-L37)

本轮时区结论仍为 **UNVERIFIED**。“未查得”限定于上述固定材料、原始提供站/作者论文的可检索内容、派生论文与提供方计划；不是声称所有上游材料均不存在时区说明。不得把无时区字符串加上 `Z` 当作已完成 UTC 转换。

## 4. 可用正常候选与已有审计的关系

本轮逐列复核印证 W1 的总数：训练72,644行，测试27,697行，特征134列、标签8列。CSV 与 MAT 的逐值一致性沿用 W1 已执行审计，本轮补充了标签列统计，不重新声称执行全部审计。

| 项目 | 训练 | 测试 |
|---|---:|---:|
| 八列全零候选 | 2,874 | 0 |
| 仅后四列非零、前四列全零 | 69,770 | 26,765 |
| 四类人工攻击并集 | 0 | 932 |
| blacklist 正值 | 69,770 | **全部27,697** |

训练八列全零行集中在无时区时钟 `201605300006`—`201605312359`，连续2,874分钟；其前一行的 `blacklist` 仍为正值。测试全部行 `blacklist >= 42`；后面三列在两套数据中均全零。因此“测试无全零候选”的直接载荷原因是 blacklist 全覆盖，不能归咎为 udpscan/sshscan/spam 全覆盖，也不能称标签列被读反。

冻结政策下，2,874行只是正常候选供应量，不证明能满足训练、验证、独立校准三段及连续历史要求；测试正常候选分母为零，FPR 与正常高负载 FPR 均不可计算。没有来源证明全零标签意味着绝无漏标攻击。

README 把 v3 测试写为43,200行，与固定 MAT/CSV 的27,697行不一致。派生论文 §3.3 说明 v3/v4 对真实异常采用解析后删除整分钟观测的处理；这支持“分钟可能已筛除”的一般解释，但没有逐行清单，不能据此确认全部15,503行差额的成因。论文还报告背景漏标问题，因此其评价中的“正常”不能直接替代本项目冻结正常候选定义。[固定 README](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/README.md)、[派生论文，§3.3—3.4](https://www.mdpi.com/2306-5729/10/3/33)

## 5. 待决定事项与授权边界

以下是协议冲突与待补证据，不是本轮已经采用的方案：

1. **时区证据不足**：需要提供方针对 v3 生成链的时区声明或可复核运行配置，才能冻结四个 UTC 区间。采集地点与 Git 时间不能填补此项。
2. **正常样本供应不足**：固定载荷与八列全零政策共同导致测试无正常候选。继续保留现政策则 Data Gate 不通过；若考虑放宽 blacklist、改变数据版本/范围或另设弱标签评价，均属研究协议调整，须由用户决定后另行记录，不可追认为已经授权。
3. **标签可信度边界**：blacklist 是有来源的可疑活动标签，既不能全部认证为攻击，也不能整列认证为正常。任何重新标注都需要独立证据与新的评价定义。
4. **许可文本不一致**：固定仓库 LICENSE 是 GPL-3.0；提供方2024数据管理计划 §2.3.3 也明确写数据可按 GPL-3.0 重用；2025派生论文首页另写 Dataset License: CC-BY-NC。两份第一方数据声明并不一致，本轮不裁定优先级，也不公开再分发载荷。注意论文自身的 CC BY 文本许可与数据许可是两个对象。[仓库 LICENSE](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/LICENSE.txt)、[数据管理计划，第4页](https://codas.ugr.es/animalicos/doc/deliverable3.pdf#page=4)、[正式论文首页](https://www.mdpi.com/2306-5729/10/3/33)

后续可进行提供方证据补查或形成供用户审阅的协议候选；本轮没有发送对外询问信息，也没有替用户选择上述调整。真实 IF、当前 AE、历史增强 AE、窗口选择、三种子实验、容量匹配和正式比较仍为 **NOT_RUN**。

## 6. 可复核性说明

GitHub README、递归目录、FCParser 文本使用已连接的 GitHub 只读工具取得。原始提供站和作者 PDF 的直接打开返回403；其标签表、背景与黑名单说明通过该第一方 URL 的搜索索引文本核查，不冒称完整 PDF 已成功下载阅读全文。MDPI 直接打开曾返回429；出版信息与相关章节通过同一正式论文 URL 的索引正文核查。ANIMaLICoS 数据管理计划 PDF 可直接读取。检索未获得时区证据。

本地仅使用标准 CSV 读取和 scipy.io.loadmat 读取既有文件，统计标签正值、范围、时间与 MAT 元数据；没有写回原文件，也没有训练或评分。

## Data Gate重审补充

后续同日独立核查已直接取得Granada机构版正式PDF及机构数据入口HTML，补强此前索引证据；许可范围重叠差异仍未解决。classM应解释为HHMM，而非午夜后累计分钟。本记录的首次访问限制作为历史保留，当前结论见[时间核查](2026-10-21-data-gate-time-semantics.md)、[来源许可](2026-10-21-data-gate-source-license.md)及[Gate判定](../project/DATA-GATE-2026-10-21.md)。
