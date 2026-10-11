> 公开归档副本。保留原文版本与当时状态；当前进度以仓库项目规划和最新报告为准。原始附件与个人信息留在本地。

# Report Figure Design Spec

## scope
- requested_artifact: three standalone opening-report figures
- source: opening report V0.7, sections 4.1, 4.3, 4.4
- audience: undergraduate opening-report reviewer
- status: proposed work and candidate implementation
- output: editable SVG, high-resolution PNG, grayscale PNG, source YAML, usage guide
- workflow_adaptation: User requests figures for the existing Word report. Apply the internal TechnicalRoute contract, template selection, shape, typography and source checks to figure assets. Deck intake, AI comparison pages, deck notes and PPTX export are outside this requested artifact.

## colors
- primary: #1F4E79
- secondary: #2E7D32
- accent: #A23B2A
- muted: #64748B
- surface: #F5F8FB
- text: #182636

## typography
- chinese: Microsoft YaHei
- latin: Times New Roman
- title_px: 32
- heading_px: 26
- body_px: 24
- small_px: 21

## geometry
- canvas_width: 1200
- corner_radius: 6
- connector_width: 2.5
- image_width: 3600
- image_dpi: 600
- recommended_word_width_cm: 16

## forbidden
- additional_models: No Transformer, GNN, LLM or online adaptation module.
- results: No performance values, empirical curves or completed-test claims.
- data_status: UGR16 FeatureData remains a candidate.
- leakage: Evaluation labels do not enter detection or history updates.
- source_preservation: Original report and prior figures are retained.
