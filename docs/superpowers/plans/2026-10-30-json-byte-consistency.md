# JSON 摘要与解析共用字节

日期：2026-10-30。状态：IMPLEMENTED_SYNTHETIC_ONLY。从 `d45fc1a` 续接，保留[Parquet读取修复](../../guides/parquet-byte-consistency.md)。

## 问题与范围

后端在初始文件摘要通过后另行读取JSON解析，未把解析输入与原manifest摘要绑定。已有只读模拟在metrics.reason单字段合法改变时得到错误HTTP200；本批先在全新临时合成包物理替换复现，其他评价字段保持。

统一处理summary.json、config.json、metrics.json、model/metadata.json、model/preprocess.json五个manifest文件项。根manifest没有上级摘要，保留一次读取解析，不编造自认证、签名或新契约字段。reason和高负载业务语义不变，核心包独立loader等其他入口不扩大。

## 最小决定

read_json增加仅关键字expected_sha256=None：取得一次data，如有原期望则先核data摘要，再把同一data交给原model parser。五处正式调用分别传本次verified_hashes中的原SHA，不刷新manifest或以重序列化相等替代原字节身份；合法空白变化也必须拒绝。

保留初始digest、路径/资源/模型兼容检查和错误顺序。JSON原先已全量read_bytes，本改动对同一对象hash和parse，不新增第二份整文件副本或常驻缓存；不承诺零分配或精确峰值。无expected的根manifest/直接调用仅作类型解析，不具备上层摘要保证。

## 执行与验收

- [x] 独占测试任务以新tmp包物理改写metrics.reason及其他四JSON合法空白，保存有效RED；核原摘要、目标parser前拒绝和安全错误。
- [x] 主控最小修复，相关后端回归；原空值、说明、指标/区间、通道和三类导出保持，独立审查。
- [x] 主控实际新Fake任务验收正常与五类物理替换，旧目录只读核身份，记录根manifest无上级摘要边界。
- [ ] 维护状态/README/路线图/日志及既有知识笔记，仓库检查后由GitHub Desktop提交推送，核对远端和CI，不合并main。

主控独占源码/公共材料，内部任务独占测试、私有验收和只读审查。只做SYNTHETIC_ONLY工程修复；不新增真实CSV读取/下载、模型拟合/训练/评分/Q99或正式实验。生产134/268契约、研究政策与真实证据保持，Data Gate BLOCKED。
