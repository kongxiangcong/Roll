# 16 规格审查：接手复核与评测纠正

日期：2026-10-18，Asia/Shanghai。基线 `b4fb4407a9e6e91876f314ac9ad5bde7d0e7f35e`。单代理对照 issue 16 / spec ID-10 审查，非独立人工审阅。

- 15 已 complete；第16票产品源码、API测试与浏览器配置在动手前匹配原验收指纹（`inherited-code-verification.json`）。上一实施会话 `01a13cba-8af2-7bf3-9628-b1f36da1eb4a` 为 notLoaded，最后一轮 completed；未发现其他活跃同目录会话。初始 Git 状态379条，既有修改全部保留。
- 模型条件仍未满足。HF搜索FinBERT2得到9个公开仓库，无分页Link；官方组织4个模型。官方base/large为BertForMaskedLM；Narsil是英文，Jagannathetgw无权重，Czunzun是英文DistilBERT衍生/MLM，penrosepls是预训练副本；Riverise虽有FinBERT2微调权重，但其任务为Non-Envir/Envir及Data/Action/Gain/Regu/Vague环境主题，且未见README或许可证。不能作为中文正负情绪checkpoint下载接入。此结论限于核查的公开仓库，并非证明所有私人或其他平台均不存在。
- 具体替代资源已核对：`yiyanghkust/finbert-tone-chinese`，版本 `e91b1a3af10e1e8c9c03429d3cd7d5e9a1c8000d`，Apache-2.0，BertForSequenceClassification，0中性/1正向/2负向，约409MB。它不是FinBERT2。卡片声明约8k私有分析师报告句训练，不能核验训练集或将卡片0.87 F1当本地验收。已询问用户是否允许按原验收评估此替代；未下载权重、未替换组件、未训练。bardsai另有三类候选，但卡片示例将营收增长判负，未运行或据其卡片指标作选择。
- 原120/30分割不满足时间隔离：design覆盖2026-08-09至10-16，holdout覆盖09-08至09-15；holdout无中性支持。精确URL/hash分成150组不证明语义事件隔离，例如设计集index0/1均描述2027—2029关联交易合同。旧留出集已经看过，不能再称未见数据。
- 原评测代码漏计被拒判的正负样本为FN，也未把中性/不相关误判纳入二类precision的FP。新增 `sentiment_evaluation.py` 和独立纠正报告，原标签、推理结果、混淆、门槛和旧报告均不改。按全体真值样本纠正后，合并二类macro-F1=0.563218，P recall=46/53=0.867925，N recall=6/30=0.200；中性支持18、不相关49，其直接分类召回均为0，拒判数分别12/44。总拒判仍0.540，旧测得p95仍0.3687s（不是本轮重新评测150条）。
- 新reference公开真实各类support/TP/FN/FP/recall/confusion和指标版本；旧保存包仍绑定旧reference并原样重放，页面显式标“旧评测口径…不作验收依据”，不静默改写历史。新分类包使用纠正后的reference；没有改变模型、标签映射、拒判层或门槛。
- 16仍partial/needs-info，17→18/22→26依赖未解除。下一步需选择可用checkpoint路线，并在任何新候选推理前冻结事件组与时间互斥切分及各类支持；现有150条仅可作为已暴露的非独立诊断材料，不能追认旧评测通过。
