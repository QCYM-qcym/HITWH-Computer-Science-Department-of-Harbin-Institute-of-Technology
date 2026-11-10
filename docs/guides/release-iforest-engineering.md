# 保存输入的隔离森林工程入口

日期：2026-11-10。状态：最终源独审与修订复审、4067项完整本地回归及新安装后的两个实际人工模型视图通过；末次运行证据独立复核通过，本地工程接受。依据：[设计](../design/release-iforest-engineering-v1.md)、[实施计划](../superpowers/plans/2026-11-10-release-if-engineering.md)、[验证记录](../research/2026-11-10-release-iforest-engineering-verification.json)。

该入口把已保存、已配对的候选13/26维输入交给固定隔离森林。检查保存身份、时间轴和资格人口后，只向模型传数值；预处理拟合、模型训练、独立校准的样本分别保留。当前13维与历史增强26维使用同一共同有效分钟。它是Python内存接口，未新增任务API、网页、命令行或模型保存格式。

在已有锁定CPU模型依赖的环境中，调用方式如下。将两个占位目录替换为已验收人工示例包的绝对目录；此段是用法，实际执行结果单列于验证记录。

```python
from pathlib import Path
from traffic_anomaly.release_minute_package import load_release_minute_package
from traffic_anomaly.release_input_package import load_release_input_package
from traffic_anomaly.release_model_inputs import pair_release_model_inputs
from traffic_anomaly.release_iforest import fit_release_iforest, summarize_release_iforest

raw = load_release_minute_package(Path("ABS_RAW_DIR"))
prepared = load_release_input_package(Path("ABS_PREPARED_DIR"))
pair = pair_release_model_inputs(raw, prepared)
result = fit_release_iforest(pair, view="h30_26")
summary = summarize_release_iforest(result)
```

`view`只接受`current13`或`h30_26`，必须显式填写。配置固定16棵树、最多32个训练样本、种子42、单线程，属于工程默认。模型只拟合训练资格行；只用独立正常校准分数的线性99%分位数定阈值，严格超过才报警。合法训练或校准人口为零会在加载模型依赖前安全拒绝。

`result`提供全轴`scores`、`predictions`和`scored_mask`。无效分钟的分数和预测均为`None`，不得计作正常负例。结果保留原始包、准备包和配置身份，不包含标签或可变模型。`summary`仅输出白名单配置、身份、人口和阈值；它不重算Q99，不能认证一个自洽的手工结果或外部文件字节。

最终专项117项包含在相关281项中，范围不累加。完整回归与安装后真实sklearn的人工双视图运行分别记录，源码单测不替代它们。真实C17数据的处理、训练、评分、阈值校准和正式比较仍NOT_RUN，S2/Data Gate保持BLOCKED；本入口不完成生产134/268迁移，也不提供检测效果结论。

本轮实际从新core wheel安装到仓库外新target（73个wheel成员、76个安装成员），受控透明observer原样转发真实sklearn与校准器，记录2次fit、2次score_samples和2次Q99。两视图均176分钟、共同56、无效120、训练18、独立校准10；阈值分别为0.5634703452851734与0.5734566900037，均通过独立线性分位数验算。原包、源码、复制源、wheel和安装保持；依赖复用既有venv，不称全新依赖环境。该运行不提供检测效果或高负载结论。

最终源完整本地回归4067通过、20跳过、1项既有TestClient警告、56子测试；其中包含281相关及117专项，不能相加。两次实际模型消费、旧候选单测模型和真实C17数据实验分别记录，最后一项仍未开展。

异常输入的索引长度预检加入后，当前源已在全新target复验。修后第一次控制器将JSON列表与内存元组直接比较，整轮失败且未接受；原始失败、两视图已观察数值和缺失项保留。随后仅修私有比较表示，先完成29项纯比较检查，再以新目录、新冻结运行完整V3验收。V3完整视图（含观察记录）与初版严格相等；各轮实际调用次数单列，不充当研究重复实验。算法使用scikit-learn，输入核验、时间资格、独立校准及结果接口由项目代码实现。
