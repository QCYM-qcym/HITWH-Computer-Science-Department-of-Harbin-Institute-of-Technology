# 候选合成结果查看页

日期：2026-10-31。状态：IMPLEMENTED_SYNTHETIC_ONLY。范围：SYNTHETIC_ONLY。依据[本批计划](../superpowers/plans/2026-10-31-candidate-viewer.md)，消费[独立候选HTTP](candidate-readonly-http.md)已保存的结果。原Vue四页、生产契约与任务后端保持原用途。

页面入口为 `/candidate`。固定同源资源只有 `/candidate/viewer.css` 和 `/candidate/viewer.mjs`；无CDN、在线字体或新依赖。受信本地代码先按[只读HTTP启动说明](candidate-readonly-http.md)核验人工运行与输入快照，再将工厂导入及调用换为：

```python
from traffic_api.candidate_viewer import create_candidate_viewer_app

app = create_candidate_viewer_app(registrations)
```

这里的registrations是已有的1–4个CandidateRegistration配对，不是服务器路径或网页输入。仍只绑定127.0.0.1空闲端口、单worker、无reload。浏览器打开该端口的 `/candidate`；该地址没有尾斜杠，资源使用固定同源地址。页面不创建任务、运行模型、导出文件或决定研究政策。

先选择目录中的原run_id，再应用分钟范围与页大小。表单草稿与已应用范围分开；Apply回到第一页，前后页沿用已应用范围。运行、页或范围变更会清除过期详情。页内条数、匹配总数只是查询结果行数，不是正常或攻击评价分母。空页和查询失败分别显示，不用旧运行内容填充新选择。

图表横轴是当前页记录顺序，不是已认证的物理持续时间；原始源钟面不转换为UTC或机器本地时间。只画本页原分数和保存阈值，在null与原break_before处断线，不抽样、不平滑、不插值。阈值以虚线及空心点显示，单点页也保留可见参考标记。完整分钟表可选择无效行查看原因。0分不等于缺失，alarm=false不代表正常标签；空页没有阈值条目时清除旧阈值。

详情按13个特征的原顺序列出raw、prepared、H15与H30偏离，各自按有效掩码显示。即使共同评分无效，也保留已有单独通道。三政策分类与原攻击标签存在标记属于审计元信息，不自动选定最终政策。AE的当前/历史重构只显示已保存的组标量MSE：APPLICABLE但值为null、NOT_APPLICABLE与逐特征NOT_STORED分别解释，不能分摊为虚构的逐特征误差。

页面只引用完整保存评价的scope、run_id、SHA与字节数；不按当前页重算FPR/FNR、分位点或模型排名，也不把摘要伪装成下载链接。始终显示人工证据和审计政策标记；缺来源重放证明时不升级为VERIFIED。

三个静态文件在wrapper启动时通过包资源读取并缓存；单文件最多1MiB、合计最多3MiB，缺失、空文件、非UTF-8或超限时拒绝启动。请求不读取任意文件。后端wheel需要实际包含并能从隔离安装位置读取三资源；editable工作区或原Vue构建不代替此验证。原Vue构建不打包或类型检查这个独立MJS，相关JS测试单独发现和记录。

包装器新51项/相关128项、候选DOM31项/前端总56项通过；原Vue类型、构建与契约检查通过。实际wheel安装核对模块来源及三资源字节，实际浏览器复验单点阈值、无效/有效详情、范围分页、空页与安全错误。初次JS测试加载偏差与真实UI缺陷均记录在[完整证据](../research/2026-10-31-candidate-viewer-verification.json)。HTTP测试、DOM测试和实际浏览器操作分别记录；它们不证明真实检测效果。真实CSV、下载、预处理拟合、真实模型训练评分校准及正式实验均未启动，主数据与最终Attempted政策仍待决定，Data Gate仍BLOCKED。
