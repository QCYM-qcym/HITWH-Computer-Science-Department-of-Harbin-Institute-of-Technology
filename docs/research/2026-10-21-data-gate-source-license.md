# 数据来源、版本与许可对照

访问日期：2026-10-21。Work C并行核查；只读取官方文本、目录及版本元信息，没有下载其他数据载荷、对外发信或公开再分发。本记录是证据对照，不裁定冲突声明的法律优先级。

## 不可变文件身份

当前[作者仓库main](https://api.github.com/repos/josecamachop/UGR16_FeatureData/commits/main)仍指向`760863d31413739a129b3be2d1d52cde217962e8`。本地五份v3文件的Git blob SHA1与尺寸全部匹配[固定完整树](https://api.github.com/repos/josecamachop/UGR16_FeatureData/git/trees/760863d31413739a129b3be2d1d52cde217962e8?recursive=1)，SHA256见[载荷审计](../../data/AUDIT_REPORT.md)。官方目录没有额外v3周分片。2024-11-20发布的[release v1.0](https://github.com/josecamachop/UGR16_FeatureData/releases/tag/v1.0)指向较早提交，但五v3数据blob相同；仓库发行v1.0不等于UGR16v1数据变体。没有据此更换数据。

## 按对象区分

| 对象 | 第一方来源与版本 | 许可或使用条件的证据状态 |
|---|---|---|
| NESG原始流量及原流级标签 | [提供站](https://nesg.ugr.es/nesg-ugr16/index.php)、[原始论文](https://doi.org/10.1016/j.cose.2017.11.004)，2016采集、2018正式刊载 | 站点直接403，未取得明确覆盖原始文件的许可；UNVERIFIED。不把派生仓库许可倒套全部原始流 |
| ANIMaLICoS修复流量及144维中间特征 | [DMP §2.1](https://codas.ugr.es/animalicos/doc/deliverable3.pdf#page=2)，2024-11-20 | DMP对其数据总体给出GPL3重用声明；未取得具体流量交付条款，本轮未取载荷 |
| 本次134维v3特征 | 固定仓库、DMP F.3、[2025正式论文机构版](https://digibug.ugr.es/bitstream/10481/102834/1/data-10-00033.pdf)，Data10(3):33，2025-02-25 | 仓库GPL3与DMP数据GPL3；正式论文另列Dataset License CC-BY-NC、版本未指定；**范围重叠的第一方差异未解决** |
| 随包八列Y/Yt标签 | DMP F.3及论文DF.3把标签与特征一起分发 | 未发现独立标签许可，应保留相同范围差异；不能另认定标签无需许可 |
| v3专用生成/删行代码及运行配置 | 当前固定树未附 | 无法认证精确生成版本、时区、删行过程；不能以通用工具源码补全 |
| 通用FCParser代码 | [setup.py](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/bin/setup.py)明确GPLv3，版本1.0；机构fork同一提交 | 是代码许可证据。不能因根目录无LICENSE、GitHub license:null而写“无许可”，也不能代替数据许可 |
| nfdump工具 | [官方固定LICENSE](https://github.com/phaag/nfdump/blob/da169d671d0e78cfa0ff3feccc9d64f1d066a3aa/LICENSE)，BSD三条条件文本 | 仅覆盖工具；本次v3实际使用版本未核实 |
| 2025论文文本/图表 | 机构正式PDF首页 | 文章本身CC BY4.0，与单列的数据CC-BY-NC是不同对象 |

## 差异的直接依据

[DMP §2.3.3第4页](https://codas.ugr.es/animalicos/doc/deliverable3.pdf#page=4)明确写：**“Los datos son reutilizables bajo licencia GPL-3.0.”**，适用对象是前文所列数据，不只代码。[正式论文首页](https://digibug.ugr.es/bitstream/10481/102834/1/data-10-00033.pdf#page=1)则列：**“Dataset License: CC-BY-NC”**。[机构数据入口](https://codas.ugr.es/animalicos/en/results#datasets)直接链接相同作者仓库，故不能仅以“代码GPL、数据CC”消解差异，也不能擅自认定可自由二选一或较新声明自动取代旧声明。

两类声明对本地非商业、保留出处、不再分发载荷的研究均有正面支持；未查得禁止这一窄用途的条款。但CC版本、覆盖文件及声明关系未明确。此判断不等于许可链已完全核清，也不自动放行真实模型。原始流量使用条件另待核查，本轮不扩展到原始流量。

## 访问与待确认

DMP直接读取并核对许可页。MDPI直接429；Granada机构PDF通过Python内存读取成功（857,994字节、15页），直接核对首页、表2及相关章节，未下载数据载荷。机构results HTML直接200并核对指向同一仓库；GitHub只读工具核对树、release、LICENSE及源码。原始站403的部分只采用第一方URL索引，不声称已阅读全文或取得原始许可。

供用户自行询问，**没有发送**：上述精确提交五文件及8标签适用哪个许可、CC具体版本/URL、两声明是否为双许可或更正；许可是否覆盖原始/修复流量；本地非商业拟合与仅公开不可逆汇总指标是否允许。另应询问v3生成链的时区/DST、分钟桶起止和采用的flow时间字段，以及测试blacklist全覆盖是否预期。可使用[下一阶段提示词与询问草稿](../guides/real-validation-preflight.md)。
