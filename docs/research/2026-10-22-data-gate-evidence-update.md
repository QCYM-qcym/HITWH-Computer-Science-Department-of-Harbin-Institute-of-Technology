# Data Gate 增量证据与候选元数据核查

核查日期：2026-10-22。性质：公开官方文本和已有材料的只读核查；不含新载荷审计或模型运行；本轮用户随后确认C可行性方向，具体数据与表示未定。续接代码`3ef2387b62b715ffad1135d9c30f9248a599fc40`；独立分支`codex/research-protocol-decision`。当前报告仍为V0.40。启动时未在本轮附件、知识库反馈目录及版本索引中发现新的作者回复、导师决定或后续有效报告；随后用户在本聊天明确选择C方向，这属于新决定而非上游数据证据。此范围不代表检查了私人邮箱或所有沟通渠道。

**未发现能够解除三个既有阻塞的新证据。** 本轮补充摘出旧论文的blacklist名单时间范围，查到出版商历史HTML更新注记，并对两个替代候选做有界筛选。它们均不能作为当前v3已经可运行的依据。既有真实计数及SHA256沿用[2026-10-21聚合审计](data-gate-2026-10-21-audit.json)，没有重复运行全量审计。

## 官方更新与遗漏证据

以下来源均于2026-10-22核查。检索索引与直接打开分别标明；访问失败不等于上游不存在说明。

| 来源及适用对象 | 本轮证据/新增性 | 支持的结论及不能支持的结论 |
|---|---|---|
| [UGR16_FeatureData main](https://api.github.com/repos/josecamachop/UGR16_FeatureData/commits/main)、[完整树](https://api.github.com/repos/josecamachop/UGR16_FeatureData/git/trees/760863d31413739a129b3be2d1d52cde217962e8?recursive=1)；当前v3 | 直接读取成功，main仍为760863d…，完整树未截断；五v3 blob与上轮元信息相同，无新增生成配置 | 可确认本轮可见版本未前移；不能认证时区、许可关系或新增正常样本 |
| [发行记录](https://api.github.com/repos/josecamachop/UGR16_FeatureData/releases)、[全状态issues](https://api.github.com/repos/josecamachop/UGR16_FeatureData/issues?state=all&per_page=100) | 仅v1.0，发布/更新时间2024-11-20，附加assets为空；issue列表为空 | 本入口未见新公开勘误；不覆盖私人回复、已删除记录或所有站点。v1.0发行号不等于v1数据变体 |
| [固定README](https://github.com/josecamachop/UGR16_FeatureData/blob/760863d31413739a129b3be2d1d52cde217962e8/README.md)；v3元信息 | 旧说明列测试43,200行，与已有固定文件实测27,697不符；不是新文件 | 需要作者解释删行/筛选规则，不能推断漏下载分片或用文档数覆盖实测数 |
| [FCParser master](https://api.github.com/repos/josecamachop/FCParser/commits/master)、[固定源码](https://github.com/josecamachop/FCParser/blob/959c10679eefcd9479aa8522b63dc054ac5e05cd/bin/fcparser.py) | 仍为959c106…；通用window=1向分钟起点归桶机制保持 | 通用实现可复核；未证明当前v3由该版本/配置生成，不能认证v3桶端点 |
| [DMP §2.1/2.3](https://codas.ugr.es/animalicos/doc/deliverable3.pdf)、[机构入口](https://codas.ugr.es/animalicos/en/results#datasets) | 直接读取，DMP标注2024-11-20；F.3及v.1指向同一特征仓库，仍有数据GPL-3.0声明 | 加强数据对象连接，不消解与论文CC-BY-NC差异；未做PDF字节哈希比较，不称全文完全未变 |
| [原始UGR16论文Table VI后段](https://nesg.ugr.es/nesg-ugr16/dataset_AuthorVersionFinal.pdf)；原始流标签 | PDF直接403，第一方URL检索索引提供原文：名单选取覆盖采集前后各两个月，命中流不一定是攻击。是本轮新增摘录的旧依据 | 包含事后名单信息，不能声称blacklist是在线当刻已知真值；也不能认证当前v3全覆盖原因或把背景改成正常 |
| [正式派生论文](https://www.mdpi.com/2306-5729/10/3/33)、[机构PDF](https://digibug.ugr.es/bitstream/10481/102834/1/data-10-00033.pdf) | 本轮直接429/超时，第一方索引仍列Dataset License CC-BY-NC；沿用上轮直接核对PDF的证据 | 未取得新许可澄清；本轮不声称重新阅读全文。原始论文机构入口另一次502 |
| [出版商版本注记](https://www.mdpi.com/2306-5729/10/3/33/notes) | 新补查索引：2025-06-24 17:50 CEST HTML Update；2025-02-25正式PDF。直接打开429，未列改动内容 | 仅说明历史网页更新线索，不是许可勘误。索引无精确抓取时刻，不能当实时正文差异 |

本轮主控与两个核查任务交叉确认上述结果。GitHub tags端点未获工具支持，因此不声称检查了全部历史标签；实际核查的是main、完整树及release列表。未进一步扩展检索渠道，也未联系作者。

## 时间语义仍需分别确认

| 项目 | 现有支持 | 当前状态及限制 |
|---|---|---|
| 时区/UTC偏移 | 12位源钟面，无时区字段 | UNVERIFIED；不采用作者提交偏移、采集地点或机器时区 |
| DST | 既有钟面跳变与DST或删行均兼容 | UNVERIFIED；不扣除或填补推测的跳变分钟 |
| 桶起止 | 通用FCParser向起点归桶 | v3 UNVERIFIED；需要精确生成配置绑定文件版本 |
| 标签/特征时间基准 | 上轮X/Y/MAT逐行钟面一致 | 文件连接VERIFIED；上游流开始/结束字段与标签聚合端点尚未认证 |
| classM | 上轮逐值核对为HHMM | 保留该含义，不当日内累计分钟或独立时区证明 |

源钟面格式检查与文件连接仍可成立；真实经过H分钟、绝对UTC边界、按日/时段解释尚不能据此认证。完整流统计何时可用以及blacklist的事后来源，需要与模型的因果输入规则分别记录；本轮没有发现或指控模型使用标签作为特征。

## 使用条件按对象保留

| 对象 | 声明/证据 | 本轮判断 |
|---|---|---|
| 原始流量及原始流标签 | [原始提供站](https://nesg.ugr.es/nesg-ugr16/index.php)仍403 | 使用条件UNVERIFIED，不把派生许可倒套原始数据 |
| 最终v3衍生134维特征 | DMP/仓库数据GPL-3.0，正式论文数据CC-BY-NC | 范围重叠差异UNRESOLVED，CC版本与许可关系需明确 |
| 随包八列标签 | DMP将其与特征一起分发，未见独立许可 | 同样保留差异，不认定标签豁免 |
| 配套代码 | 上轮FCParser GPLv3、nfdump BSD证据；当前v3精确生成代码缺失 | 工具许可不代替数据许可，不证明生成版本 |

继续只读核查沿用上轮窄范围判定；本地非商业用途不能视为许可链已核清。真实拟合/评分/校准准入未满足，公开数据载荷再分发未获本轮清理。

## 补充或替换数据的有界筛选

筛选限以下两个官方数据入口及关联AWS登记页，状态均为**METADATA_ONLY / NOT_SELECTED**。网页日期和官方标签说明不等于文件审计通过。未下载CSV、PCAP或压缩包，未核算新载荷样本数。

| 项目 | CICIDS2017 | CSE-CIC-IDS2018 |
|---|---|---|
| 官方范围线索 | 2017-07-03至07-07；周一benign，之后混合正常与攻击；80余流特征 | 官方给采集/攻击日期与钟面、正常生成机制；CICFlowMeter流特征 |
| 使用条件 | 机构License段公开供研究使用并要求引用，未给标准许可名称/版本 | 机构License段允许转载/镜像/再分发，要求引用并链接AWS登记；不擅标CC版本 |
| 尚缺证据 | 精确文件/校验、时区/DST、流时间字段、正常分钟与四段供应、连续性 | 同左，另需核资源规模及前段连续正常供给 |
| 特征兼容 | 不是UGR134维分钟计数；需新聚合/标签适配，可能新d/2d契约 | 同样不兼容；不能按特征概述先冻结具体列数 |
| 本轮判断 | 正常日在前的结构支持优先可行性审计；一日正常是否足够三段及代表性未知 | 第二候选；许可文字较明确，但连续正常供应和有界载荷仍待核 |

来源：[UNB CICIDS2017](https://www.unb.ca/cic/datasets/ids-2017.html)、[UNB CSE-CIC-IDS2018](https://www.unb.ca/cic/datasets/ids-2018.html)、[AWS登记及许可回指](https://registry.opendata.aws/cse-cic-ids2018/)。本轮直接读取网页。另从UNB官方链接进入[CICIDS2017下载入口](https://cicresearch.ca/CICDataset/CIC-IDS-2017/)，页面显示要求姓名/邮箱等资料的表单及Server error；未填写或提交个人信息，未取得文件清单、大小或包内字段。该限制不证明数据不可用，需后续合法可访问入口或用户提供已取得文件。AWS存储区域不是采集时区证据；流级BENIGN不自动证明聚合后整分钟正常。以上仅筛选理由，无候选被认定可替代当前数据。

## 本轮可交付与未执行项

新增交付为[三路径协议对照](../project/RESEARCH-PROTOCOL-OPTIONS.md)、[八项Gate判定](../project/DATA-GATE-2026-10-21.md#2026-10-22-八项准入复核)及[更新后的询问稿/条件清单](../guides/real-validation-preflight.md)。原审计计数、公共字段及研究政策未变，未发现本轮需要修改业务代码的新错误。

本轮不重复全量真实审计、业务训练测试或浏览器联调；真实工程验证和正式实验均NOT_RUN。文档/状态维护检查单独记录，不将上一轮129项远端测试写成本轮重新运行结果。


本地文档验收：仓库13项测试、进度一致性和隐私/作者检查通过；172个本地链接有效。额外人工算术检查仅调用既有指标函数：10个攻击分钟、3次检出得到fpr=null、precision=1、recall=0.3、f1=6/13，支持协议中对单类退化的说明，不是模型运行。无业务代码变更；完整真实审计和真实模型仍未重新运行。
