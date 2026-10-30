# 候选结果的只读查看命令

日期：2026-10-31。范围：SYNTHETIC_ONLY。用途：从已有候选人工运行包输出[曲线分页](candidate-series-pages.md)或[单分钟详情](candidate-minute-details.md)，无需另写调用代码。依据[本批计划](../superpowers/plans/2026-10-31-candidate-view-cli.md)。不创建运行、不训练模型，也不写入产物。

在已安装核心包的独立环境中执行。公共目录参数放在子命令之前；以下目录名仅为示例，应替换为本地已生成的相应人工包，不表示仓库附带这些运行产物。

```text
python -X utf8 -m traffic_anomaly.candidate_view_cli --records .runtime/P_U-adapt --inputs .runtime/P_U-inputs --if-run .runtime/if-run --source-fixture tests/fixtures/g13u-records-v1.json series --start 2026-01-01T00:00 --end 2026-01-01T00:32 --page-size 20

python -X utf8 -m traffic_anomaly.candidate_view_cli --records .runtime/P_U-adapt --inputs .runtime/P_U-inputs --ae-run .runtime/ae-run --source-fixture tests/fixtures/g13u-records-v1.json detail --timestamp 2026-01-01T02:20
```

`--if-run`与`--ae-run`必须且只能选一个。当前AE、H15或H30历史AE都用`--ae-run`，以包内已验证配置为准；选错模型类型时返回错误，不自动改用另一个加载器。records和inputs必填，`--source-fixture`可省略，省略时来源重放保持NOT_PROVIDED。

series支持`--start`、`--end`、`--page`、`--page-size`；默认开放范围、page=1、page_size=100，最大1000。先按左闭右开范围过滤，再分页；保留无效分钟、原索引、原前驱断点及完整评价引用。页行数不替代正常或攻击评价分母。detail必填`--timestamp`，保留独立特征/标签、各历史有效性和已存重构通道；无结果或预热不得显示成0。

时间沿用无偏移的整分钟源钟面，只接受`YYYY-MM-DDTHH:MM`、`:00`、`:00.000000`三种形式。Z、偏移、24:00、非零秒和非法日期不接受；不会转为机器本地时区或认证UTC。参数名不接受缩写。解析失败不加载文件；格式正确但语义非法的查询由既有查询函数在加载后拒绝。

成功时exit=0，stdout为原查询返回的单个紧凑JSON，stderr为空。先完整序列化并验证非有限值，再按UTF-8编码计数，包含末尾一个LF最多1MiB。采用二进制stdout写入已经计数的字节，避免Windows文本换行把LF扩成CRLF；这限制的是输出，不是输入读取量。超过限制返回RESOURCE_LIMIT，不输出截断JSON。

预期失败时exit=2、stdout为空，stderr只有一条`{"error":"CODE"}`。解析错误为INVALID_ARGUMENTS；查询错误沿用INVALID_QUERY、MINUTE_NOT_FOUND、INCOMPATIBLE_SNAPSHOTS或INCOMPATIBLE_SNAPSHOT；输入与运行验证错误沿用加载器代码。无法序列化的查询结果为INVALID_RESULT。错误不回显私人路径、参数值、异常原因或堆栈。`--help`按常规帮助显示并退出0，不加载运行。

加载阶段沿用[IF](candidate-run-verification.md)和[AE](candidate-ae-run-verification.md)的有界文件检查，并验算保存的预处理、历史、阈值/报警和评价关系；这不等于新拟合或模型训练评分，也不能称整个命令零复算。IF权重只作有界字节检查，AE不重建网络。加载之后的纯查询不再读取文件或重算上述量。

series只调用所选运行加载器一次；其内部仍会验证上游输入。detail还需单独加载输入快照，再按五组身份、配置和完整轴配对，因此会重复读取部分上游文件；不承诺全命令单次读取或目录原子快照。两个快照之间有变化时由配对规则拒绝，不绕过验证直接读取原值。

命令不提供输出文件、重新训练、任务数据库、HTTP或网页选项。若用户自行重定向stdout，应选择独立结果位置，避免覆盖输入包。调用不改变最终Attempted政策、主数据采用或134/268生产契约；Data Gate仍BLOCKED，真实训练评分校准和正式实验NOT_RUN。

新增59项CLI边界测试先失败后通过；相关193项通过，其中旧detail测试准备合成toy模型。主控实际21次python -m为18次成功和3次预期失败，stdout合计22859字节、stderr91字节；另2次独立受控main探针通过。39个旧文件SHA/大小/mtime及成员保持，独立审查复核23例原始流与退出码。[实际记录](../research/2026-10-31-candidate-view-cli-verification.json)。实际子进程执行与另外插桩的模型调用监测分别记录，不把未插桩的进程声称为已经全面监测。
