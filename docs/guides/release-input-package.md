# 发布记录准备输入包使用与验收

日期：2026-11-07，Asia/Shanghai。本批已获本地人工工程接受，状态为 `LOCAL_ENGINEERING_ACCEPTED_PUBLICATION_PENDING_DESKTOP`；发布 `PENDING_DESKTOP`，本批新远端 CI `NOT_RUN`。这里只记录准备包 Python 接口；CLI 另批验收，本文不预填其完成。

入口：[格式与精确字段](../design/release-input-package-v1.md)、[机器可读验证记录](../research/2026-11-07-release-input-package-verification.json)、[上游原始分钟包](release-minute-package.md)。数值与编解码在 [release_inputs.py](../../src/core/traffic_anomaly/release_inputs.py)，保存和加载在 [release_input_package.py](../../src/core/traffic_anomaly/release_input_package.py)。

## 使用前确认

输入必须是显式加载或构造后通过检查的 `c17-release-minute-package-v1` 原始分钟包。准备包独立于旧 candidate/生产 134/268 维链，不能把其身份改为旧人工格式来接模型。

每次明确指定 epsilon 和 P_U/P_B/P_A 中一个审计拟合政策。没有默认政策，也不按预测效果选择政策；三套标签和资格始终分别保留。H15/H30、fit_window=30、列序与分钟粒度固定。来源保持未认证，时间仍为源钟面完成代理，不补 UTC。

以下仅示范 Python 调用方式；本次编写文档没有重新执行示例。真实输入的读取、拟合或下游运行必须符合另行批准的范围。输出目录应是本轮新建、绝对本机路径；已有目录会拒绝覆盖。

```python
from pathlib import Path

from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
from traffic_anomaly.release_inputs import (
    ReleasePreparationConfig,
    prepare_release_inputs,
    verify_release_input_derivation,
)
from traffic_anomaly.release_input_package import (
    load_release_input_package,
    save_release_input_package,
)
from traffic_anomaly.release_minute_package import load_release_minute_package


def prepare_and_save(
    raw_directory: Path,
    new_output_directory: Path,
    *,
    epsilon: float,
    audit_fit_policy: str,
):
    upstream = load_release_minute_package(raw_directory)
    config = ReleasePreparationConfig(
        schema_version=1,
        numeric_rules_id="c17-release-log1p-mad-input-rules-v1",
        feature_names=G13U_FEATURE_NAMES,
        windows=(15, 30),
        fit_window=30,
        epsilon=epsilon,
        audit_fit_policy=audit_fit_policy,
        policy_status="AUDIT_ONLY",
    )
    prepared = prepare_release_inputs(upstream, config)
    return save_release_input_package(prepared, new_output_directory)


def reopen_only(prepared_directory: Path):
    # 不访问上游 CSV，不拟合、不重算变换或历史。
    return load_release_input_package(prepared_directory)


def replay_saved_parameters(raw_directory: Path, prepared_directory: Path):
    upstream = load_release_minute_package(raw_directory)
    saved = load_release_input_package(prepared_directory)
    # 使用保存 mean/scale，重放变换与历史；不重新估计 mean/scale。
    return verify_release_input_derivation(upstream, saved)
```

这里从旧模块只引用固定特征名常量，不创建旧 candidate 对象或使用其 SYNTHETIC_ONLY 授信字段。保存/加载 API 接受 Path；错误向调用方抛固定代码的 `ReleaseInputPreparationError`。调用者仍应自行处理异常，不能把未捕获 traceback 当作已脱敏界面。

## 读懂准备结果

`minutes.current_values` 为 N×13；`joined(15)` 或 `joined(30)` 为 N×26，只拼一套历史。对应历史无效时 joined 全行 None，即使当前13仍有限。历史不足或非有限都不表示正常0分，包内本来没有模型分数。

raw_valid、prepared_valid、H15/H30.valid、common_valid 分列。common 为当前与两窗口有效性的交集，不是所有 raw 有效分钟，也不包含未来模型评分有效性。原因保留 source_invalid、nonfinite_transform、warmup、boundary、invalid_input、nonfinite_history；gap 只作防御枚举，合法本版上游段内轴完整。

raw fit_mask 选 train 中当前及前30分钟均有效正常的当前行，每行一次。log1p 后拟合 mean/总体 std；常数列 scale=1。最终训练/校准资格还要满足 prepared 全历史正常与 common。人工 C 实际 fit=50 而 common=19，不能用19改写拟合人数或再次拟合。

普通 load 的结论为保存内容内部一致，不认证数值来源；它核摘要、类型、mask、历史状态机，不等于零计算。显式 verify 使用保存参数重算，仍不证明参数的原始拟合过程。完整自洽重写可能通过且身份改变，SHA 不是数字签名。

## 文件与恢复边界

包恰有 preprocess.json、inputs.json、labels.json、manifest.json、COMPLETE.json。上限分别为16KiB、16MiB、2MiB、64KiB、4KiB，总20MiB；最多10000分钟/7段，上游其他规则不变。标签留在 labels，模型输入中没有标签。

save 先检查内容再独占目录，最后写 COMPLETE，并回读核对。拒覆盖、额外成员、链接、变化中的包和非规范 JSON；无自动重试或清理。失败后保留实际目录用于诊断，不以“有 COMPLETE”替代成功返回。晚期失败可能留下可加载包；不承诺跨文件原子性或断电耐久。固定代码及准确分类见设计附录 A8。

## 已完成的人工验证

以下是既有收据的整理，不是本次文档编辑新运行的测试。各阶段范围及计数有重叠，不相加为新的总测试数。

| 阶段 | 实际结果 | 适用范围 |
| --- | --- | --- |
| A8 联合切片 | 469 collected；463 passed、4 skipped、2 deselected；10.92秒 | 六个指定测试文件，当前 pytest 进程守卫 |
| A9 原预算三次 | 每次 M1 超时失败，M2/M3 NOT_RUN | 120秒含10秒回收；工作约110秒，无最终 guard 收据 |
| A9 修订预算一次 | M1/M2/M3 均通过 | 仅A9改为360秒含10秒回收，10000分钟内存 codec 形状 |
| A10 安装后人工接缝 | 7条成功准备/保存/加载/重放，1条预期无训练人口拒绝，8条负例通过 | 44个验收叶进程，加4个构建/安装进程；不是44项单元测试 |

A8 的4跳过来自平台或真实链接条件；不能算对应拒绝断言已通过。2 deselected 为既有 raw 最大形状测试，不是本次 A9。前后64份 core 与15份测试相关文件身份一致，当前 pytest 模型/网络/派生进程尝试为0；这不等于所有进程或 OS 隔离。早期缺模块/夹具失败与有效 RED 分开保留，后续修复计数不累加。

### A9：预算修订与容量证据

原 attempt01/02/03 均只执行 M1，到约110秒工作限后强制结束、回收、退出1；三次失败保留，零自动重试。没有最终守卫收据，不能补记守卫通过。

主控明确只将 A9 每子进程总限从120改为360秒，仍预留10秒回收。三个固定形状、成员/总包硬限、10000分钟、256MiB任务目录、单日志1MiB及行为限制不变；A10和构建安装预算未变。

| 形状 | inputs字节 | labels字节 | 五成员总字节 | 受监督经过秒 |
| --- | ---: | ---: | ---: | ---: |
| M1 | 7233897 | 1799902 | 9036869 | 200.864 |
| M2 | 2850032 | 1829812 | 4682914 | 191.015 |
| M3 | 2290131 | 1763296 | 4060135 | 191.330 |

各10000分钟；M1/M2单段单源，M3为7段/5源、9994条人工 raw 记录。M2覆盖全部历史无效形状。三次子进程均退出0、正常回收，无强制，最终 guard passed/attempts为空、stderr0，无遗漏用例。

本阶段只构造有限数值形状并验证编码/解码与再编码一致；没有实际 prepare/fit/transform/history 公式执行，也没有 CSV 聚合或模型。表中是内存成员尺寸，不是已落盘包。修订预算通过不能改写原120秒失败，不证明所有合法载荷性能或在线服务指标。监督与采样不提供 OS/RSS 硬隔离。

### A10：安装后独立进程和人口

实际离线 wheel 为158586字节，67个成员（63个包文件＋4个dist-info），对应64份含 pyproject 的源码；63个安装产品文件与冻结源码精确一致。复用既有锁定环境，不是从零安装全部依赖的复验。

44验收叶进程为聚合6、独立参考7、主prepare8、主load7、主verify7、复制load1、负例8；成功prepare内的7次save不另计进程。加构建pip1/backend2和安装pip1，共48次受管启动。均实际退出0并回收，无强制/超时/资源或清理失败；预期拒绝由驱动核对后退出0，不是CLI错误退出码证据。

六份新造人工CSV共838逻辑行、215764字节，各聚合一次。B三政策共用其raw结果，197条记录展开198分钟轴，缺失分钟保留。独立标准库参考在主prepare前固定，实际值、标签、索引、24个mask与其比较，不仅比较计数。

| 人工例/拟合政策 | 轴分钟 | raw fit | common | 资格mask数 |
| --- | ---: | ---: | ---: | ---: |
| A/P_U | 176 | 18 | 56 | 24 |
| A-L/P_U | 176 | 18 | 56 | 24 |
| A-V/P_U | 176 | 18 | 56 | 24 |
| B/P_U | 198 | 25 | 47 | 24 |
| B/P_B | 198 | 36 | 47 | 24 |
| B/P_A | 198 | 25 | 47 | 24 |
| C/P_U | 80 | 50 | 19 | 24 |

A-L 只改测试标签，A-V 只改留出值，验证训练拟合隔离与规定的数值不变性。D 报 NO_TRAINING_NORMAL_MINUTES，主prepare1/save0，fit/transform/history0，无输出，不启动D加载或重放。

| 负例 | 预期且实际错误 |
| --- | --- |
| N1 缺完成标记；N3 第六成员 | INVALID_PACKAGE |
| N2 未重签字节损坏；N5 错误下游身份 | INTEGRITY_MISMATCH |
| N4 错误上游声明；N7 错绑上游 | UPSTREAM_IDENTITY_MISMATCH |
| N6 域内索引与mask矛盾 | INCONSISTENT_PACKAGE |
| N8 重签但推导不符的有限数值 | DERIVATION_MISMATCH |

N8 先成功decode再由verify拒绝；各负例前提在预期异常捕获外检查。含负例的显式驱动调用总数为 prepare9、prepared-save8、verify9、prepared-load20、raw-load18、decode2；不冒充所有内部 codec 调用。数值入口记录 fit-state7、fit-statistics7、transform15、history28，人工预处理确实执行，不能笼统称无拟合/无重算。

前后身份表覆盖6源、14个raw/prepared/copy包、参考/投影、5个负例包和63个安装文件，均保持。最终任务11148653字节、最大日志16707字节、最慢叶进程约2.720秒，均在登记范围。44叶进程在退出处理完成后留下守卫记录；6聚合进程各打开人工CSV一次，其余38个不打开CSV。父进程没有动态文件白名单，Python事件/冻结code守卫不认证任意native行为、所有文件事件或OS隔离。

## 尚未据此完成的工作

本批没有真实载荷读取/新增下载、真实预处理拟合、真实 IF/AE 训练/评分/Q99 或正式实验；Data Gate 继续 BLOCKED。G13U 已批准且完成的发布CSV人口供应审计不回退为待审，旧 G12 失败证据保留。最终政策、主数据采用、有限真实试点、生产迁移仍须具体决定。

本包不生成误报率/漏报率或模型比较结果，不把输入 common 当正式评分分母；未建立该新格式的真实 CLI→API→网页→导出闭环。实际待决边界参见[试点准备核查](../research/2026-11-06-pilot-readiness-review.md)。本文与验证JSON的发布状态是本批记录时快照，后续准确提交/远端CI由统一维护记录补充，不循环预填尚未产生的提交号。
