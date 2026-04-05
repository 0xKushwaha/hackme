/**
 * Mock Red Mode data for frontend test mode.
 * Simulates a tournament-style persona debate without calling any LLM API.
 * 20 personas grouped into 4 trait clusters → panel debates → champion cross-debate → synthesis.
 */

export const MOCK_PERSONAS = [
  'andrej_karpathy', 'yann_lecun', 'sam_altman', 'geoffrey_hinton',
  'francois_chollet', 'andrew_ng', 'chip_huyen', 'jeremy_howard',
  'chris_olah', 'edward_yang',
  'ethan_mollick', 'jay_alammar', 'jonas_mueller', 'lilian_weng',
  'matei_zaharia', 'santiago_valdarrama', 'sebastian_raschka',
  'shreya_rajpal', 'tim_dettmers', 'vicki_boykis',
]

export const MOCK_GROUPS: Record<string, { label: string; members: string[]; champion: string }> = {
  theory: {
    label: 'Deep Learning Theory',
    members: ['andrej_karpathy', 'geoffrey_hinton', 'yann_lecun', 'francois_chollet', 'sebastian_raschka'],
    champion: 'andrej_karpathy',
  },
  systems: {
    label: 'ML Systems & Infrastructure',
    members: ['chip_huyen', 'edward_yang', 'matei_zaharia', 'vicki_boykis', 'tim_dettmers'],
    champion: 'chip_huyen',
  },
  applied: {
    label: 'Applied ML & Education',
    members: ['andrew_ng', 'jeremy_howard', 'santiago_valdarrama', 'jonas_mueller', 'jay_alammar'],
    champion: 'andrew_ng',
  },
  strategy: {
    label: 'Strategy, Safety & Reliability',
    members: ['sam_altman', 'ethan_mollick', 'chris_olah', 'lilian_weng', 'shreya_rajpal'],
    champion: 'sam_altman',
  },
}

export const MOCK_GROUP_ORDER = ['theory', 'systems', 'applied', 'strategy']

// Per-persona individual Round 1 responses (Stage A)
export const MOCK_ROUND1_OUTPUTS: Record<string, Record<string, string>> = {
  theory: {
    andrej_karpathy: `**What stands out to me:** The feature engineering is solid but the architecture choices feel overengineered for a 7K-row dataset. You don't need XGBoost — a well-regularized logistic regression with the engineered features will get you 90% of the AUC with 10% of the complexity.\n\n**The assumption I'd challenge:** "ROC-AUC is the right metric" — in deployment you pick a threshold.\n\n**What I'd actually do:** Run logistic regression first. If it doesn't hit 0.84 AUC, then bring in gradient boosting.`,
    geoffrey_hinton: `**What stands out to me:** The ethical review is perfunctory. Disparate impact on seniors (41.7% vs 23.6%) is a serious concern that deserves more than a "monitor it" recommendation.\n\n**The assumption I'd challenge:** "No ethical blockers to proceed." — the SeniorCitizen disparity IS an ethical blocker.\n\n**What I'd actually do:** Run the model with SeniorCitizen removed. If AUC drops by more than 2%, there's an ethical problem baked into the data itself.`,
    yann_lecun: `**What stands out to me:** The statistical analysis is rigorous. The chi-square results on contract type are the most actionable finding.\n\n**What everyone is probably missing:** Nobody is thinking about the temporal structure. Churn is a survival problem, not a binary classification problem.\n\n**What I'd actually do:** Frame this as survival analysis. tenure IS your time variable. Use it properly.`,
    francois_chollet: `**What stands out to me:** The feature engineering is mechanical. charge_per_tenure is good but obvious.\n\n**What everyone is probably missing:** Interaction effects. The high-risk customer is specifically: fiber optic + no tech support + month-to-month + tenure < 12.\n\n**What I'd actually do:** Create a high_risk_combo binary flag for the triple interaction.`,
    sebastian_raschka: `**What stands out to me:** The validation methodology is the most critical piece and it's the weakest part.\n\n**What everyone is probably missing:** Nested cross-validation. The reported 0.874 AUC is likely 3-5% inflated.\n\n**What I'd actually do:** Nested 5×10 CV (outer 5-fold, inner 10-fold for tuning).`,
  },
  systems: {
    chip_huyen: `**What stands out to me:** Nobody talked about data freshness. Churn patterns shift quarterly with pricing changes and competition.\n\n**The assumption I'd challenge:** That sklearn Pipeline is a good serving artifact.\n\n**What I'd actually do:** Separate the feature pipeline from the model. Version them independently.`,
    edward_yang: `**What stands out to me:** The whole pipeline is procedural. Nobody talked about composability or reuse.\n\n**What everyone is probably missing:** Software engineering. Feature stores, reproducible pipelines, typed schemas.\n\n**What I'd actually do:** Treat this like software. Type annotations, unit tests, integration tests.`,
    matei_zaharia: `**What stands out to me:** The inference pipeline isn't designed for scale.\n\n**The assumption I'd challenge:** That FastAPI + pkl is the right serving stack.\n\n**What I'd actually do:** Define the SLA first. Batch vs real-time changes the entire architecture.`,
    vicki_boykis: `**What stands out to me:** This analysis assumes the data is correct. It isn't.\n\n**What everyone is probably missing:** Data provenance. Where did this CSV come from?\n\n**What I'd actually do:** Document the data lineage before touching a model.`,
    tim_dettmers: `**What stands out to me:** Nobody talked about the compute budget.\n\n**What everyone is probably missing:** Memory bandwidth is the bottleneck in tabular inference.\n\n**What I'd actually do:** Profile the tuning pipeline first before optimizing architecture.`,
  },
  applied: {
    andrew_ng: `**What stands out to me:** The pipeline is well-structured and the analysis is sound.\n\n**What everyone is probably missing:** Error analysis. Look at which customers the model gets wrong.\n\n**What I'd actually do:** Build the model, then spend equal time on error analysis before claiming success.`,
    jeremy_howard: `**What stands out to me:** The team jumped to XGBoost without a baseline.\n\n**What everyone is probably missing:** fastai's tabular model would outperform XGBoost here with less tuning.\n\n**What I'd actually do:** Run a fastai tabular model for 5 epochs before committing to any architecture.`,
    santiago_valdarrama: `**What stands out to me:** This reads like it was built by someone who knows ML well and businesses less well.\n\n**The assumption I'd challenge:** That a churn model delivers value automatically.\n\n**What I'd actually do:** Build a simple decision tree for stakeholder communication before the real model.`,
    jonas_mueller: `**What stands out to me:** The data quality score of 7.4/10 is treated as a minor concern. It's not.\n\n**What everyone is probably missing:** Automated data validation for every feature.\n\n**What I'd actually do:** Spend 20% of project time on data validation infrastructure.`,
    jay_alammar: `**What stands out to me:** This dataset is crying out for a clear visual story.\n\n**What everyone is probably missing:** Visualisation as a validation tool.\n\n**What I'd actually do:** Build three visualisations: calibration curve, lift chart, SHAP beeswarm.`,
  },
  strategy: {
    sam_altman: `**What stands out to me:** The ROI calculation at the end is underselling this. Churn models compound.\n\n**What everyone is probably missing:** This analysis is focused on prediction, not intervention. Build an uplift model, not a churn model.\n\n**What I'd actually do:** Pair the churn model with a survey or NPS signal to understand causal drivers.`,
    ethan_mollick: `**What stands out to me:** The human side is missing entirely. Who will use the model?\n\n**What everyone is probably missing:** Change management. The retention team needs to trust the model.\n\n**What I'd actually do:** Build the model AND design the decision interface simultaneously.`,
    chris_olah: `**What stands out to me:** The model is a black box. Nobody asked what representations it's learning.\n\n**What everyone is probably missing:** Circuits-style analysis of what features activate together.\n\n**What I'd actually do:** Build probing classifiers and activation analysis to ensure the model captures real signal.`,
    lilian_weng: `**What stands out to me:** The feature importance analysis is missing. We have 27 features but no ranking.\n\n**What everyone is probably missing:** SHAP values for individual prediction explanation.\n\n**What I'd actually do:** SHAP analysis first, then prune features to the top 12.`,
    shreya_rajpal: `**What stands out to me:** There are no guardrails on this model. What stops confidently wrong predictions on OOD inputs?\n\n**What everyone is probably missing:** Model reliability engineering. Input validation, confidence thresholds, fallback logic.\n\n**What I'd actually do:** Add a reliability layer: input schema validation, OOD detection, low-confidence flags.`,
  },
}

// Champion election outputs per group
export const MOCK_ELECTION_OUTPUTS: Record<string, string> = {
  theory: `After reviewing all 5 responses in the Theory group, the strongest position was from Andrej Karpathy. His argument combines practical simplicity (start with logistic regression) with a clear decision framework (escalate only if needed). His focus on calibration over AUC and stakeholder-facing interpretability addresses the most common failure mode of churn models.\n\n## Champion: [andrej_karpathy]`,
  systems: `After reviewing all 5 responses in the Systems group, the strongest position was from Chip Huyen. She identified the most operationally dangerous gap: the entire team is building for a snapshot, not for a system that evolves. Her focus on data freshness, pipeline versioning, and calibrated retraining triggers addresses the failure mode that kills most production ML systems.\n\n## Champion: [chip_huyen]`,
  applied: `After reviewing all 5 responses in the Applied group, the strongest position was from Andrew Ng. He correctly identified error analysis as the missing step everyone skipped. His pragmatic "build then study failures" approach directly addresses the gap between a working model and a reliable production system.\n\n## Champion: [andrew_ng]`,
  strategy: `After reviewing all 5 responses in the Strategy group, the strongest position was from Sam Altman. He reframed the entire problem: prediction without causal intervention design is incomplete. His uplift modeling direction addresses the fundamental limitation that a churn score alone doesn't tell you which customers will respond to retention efforts.\n\n## Champion: [sam_altman]`,
}

export const MOCK_PANEL_OUTPUTS: Record<string, string> = {
  theory: `## [ANDREJ KARPATHY]
**What stands out to me:** The feature engineering is solid but the architecture choices feel overengineered for a 7K-row dataset. You don't need XGBoost here — a well-regularized logistic regression with the engineered features will get you 90% of the AUC with 10% of the complexity.

**What everyone is probably missing:** Ship interpretable models to stakeholders. Track calibration and business cost, not abstract curves.

**The assumption I'd challenge:** "ROC-AUC is the right metric" — in deployment you pick a threshold.

**What I'd actually do:** Run logistic regression first. If it doesn't hit 0.84 AUC, then bring in gradient boosting.

## [GEOFFREY HINTON]
**What stands out to me:** The ethical review is perfunctory. Disparate impact on seniors (41.7% vs 23.6%) is a serious concern that deserves more than a "monitor it" recommendation.

**What everyone is probably missing:** The model will perpetuate the disparity it finds. If senior customers receive fewer retention offers because they're flagged as churners, you create a feedback loop.

**The assumption I'd challenge:** "No ethical blockers to proceed." — the SeniorCitizen disparity IS an ethical blocker.

**What I'd actually do:** Run the model with SeniorCitizen removed. If AUC drops by more than 2%, there's an ethical problem baked into the data itself.

## [YANN LECUN]
**What stands out to me:** The statistical analysis is rigorous. The chi-square results on contract type are the most actionable finding.

**What everyone is probably missing:** Nobody is thinking about the temporal structure. Churn is a survival problem, not a binary classification problem.

**The assumption I'd challenge:** The 80/20 train-test split assumption. With only 7K rows, you're leaving performance on the table.

**What I'd actually do:** Frame this as survival analysis. tenure IS your time variable. Use it properly.

## [FRANÇOIS CHOLLET]
**What stands out to me:** The feature engineering is mechanical. charge_per_tenure is good but obvious.

**What everyone is probably missing:** Interaction effects. The high-risk customer is specifically: fiber optic + no tech support + month-to-month + tenure < 12.

**The assumption I'd challenge:** XGBoost will find the interactions automatically. It won't — not with 7K rows.

**What I'd actually do:** Create a high_risk_combo binary flag for the triple interaction.

## [SEBASTIAN RASCHKA]
**What stands out to me:** The validation methodology is the most critical piece and it's the weakest part.

**What everyone is probably missing:** Nested cross-validation. The reported 0.874 AUC is likely 3-5% inflated.

**The assumption I'd challenge:** "80 Optuna trials is sufficient."

**What I'd actually do:** Nested 5×10 CV (outer 5-fold, inner 10-fold for tuning).

## STRONGEST POSITION: [Andrej Karpathy]
Karpathy's position was strongest because it combines practical simplicity (start with logistic regression) with a clear decision framework (escalate only if needed). His focus on calibration over AUC and stakeholder-facing interpretability addresses the most common failure mode of churn models: they work technically but don't get used.`,

  systems: `## [CHIP HUYEN]
**What stands out to me:** Nobody talked about data freshness. Churn patterns shift quarterly with pricing changes and competition.

**What everyone is probably missing:** The retraining cadence is wrong. PSI is a lagging indicator.

**The assumption I'd challenge:** That sklearn Pipeline is a good serving artifact.

**What I'd actually do:** Separate the feature pipeline from the model. Version them independently.

## [EDWARD YANG]
**What stands out to me:** The whole pipeline is procedural. Nobody talked about composability or reuse.

**What everyone is probably missing:** Software engineering. Feature stores, reproducible pipelines, typed schemas.

**The assumption I'd challenge:** That Jupyter notebooks are acceptable for this workload.

**What I'd actually do:** Treat this like software. Type annotations, unit tests, integration tests.

## [MATEI ZAHARIA]
**What stands out to me:** The inference pipeline isn't designed for scale.

**What everyone is probably missing:** The operational requirements haven't been defined. Batch vs real-time changes everything.

**The assumption I'd challenge:** That FastAPI + pkl is the right serving stack.

**What I'd actually do:** Define the SLA first.

## [VICKI BOYKIS]
**What stands out to me:** This analysis assumes the data is correct. It isn't.

**What everyone is probably missing:** Data provenance. Where did this CSV come from?

**The assumption I'd challenge:** That a CSV file is a reliable data source.

**What I'd actually do:** Document the data lineage before touching a model.

## [TIM DETTMERS]
**What stands out to me:** Nobody talked about the compute budget.

**What everyone is probably missing:** Memory bandwidth is the bottleneck in tabular inference.

**The assumption I'd challenge:** That GPU acceleration isn't relevant for tabular ML.

**What I'd actually do:** Profile the tuning pipeline first.

## STRONGEST POSITION: [Chip Huyen]
Chip Huyen's position was strongest because she identified the most operationally dangerous gap: the entire team is building for a snapshot, not for a system that evolves. Her focus on data freshness, pipeline versioning, and calibrated retraining triggers addresses the failure mode that kills most production ML systems.`,

  applied: `## [ANDREW NG]
**What stands out to me:** The pipeline is well-structured and the analysis is sound.

**What everyone is probably missing:** Error analysis. Look at which customers the model gets wrong.

**The assumption I'd challenge:** That 0.874 AUC is good enough. Understand the Lift curve at the top 20%.

**What I'd actually do:** Build the model, then spend equal time on error analysis.

## [JEREMY HOWARD]
**What stands out to me:** The team jumped to XGBoost without baseline.

**What everyone is probably missing:** fastai's tabular model would outperform XGBoost here with less tuning.

**The assumption I'd challenge:** OrdinalEncoder for categoricals implies an ordering that affects the model.

**What I'd actually do:** Run a fastai tabular model for 5 epochs.

## [SANTIAGO VALDARRAMA]
**What stands out to me:** This reads like it was built by someone who knows ML well and businesses less well.

**What everyone is probably missing:** The business framing. "$240K annual revenue protection" needs a confidence interval.

**The assumption I'd challenge:** That a churn model delivers value automatically.

**What I'd actually do:** Build a simple decision tree for stakeholder communication.

## [JONAS MUELLER]
**What stands out to me:** The data quality score of 7.4/10 is treated as a minor concern. It's not.

**What everyone is probably missing:** Automated data validation for every feature.

**The assumption I'd challenge:** That the 11 TotalCharges nulls are the only data issue.

**What I'd actually do:** Spend 20% of project time on data validation infrastructure.

## [JAY ALAMMAR]
**What stands out to me:** This dataset is crying out for a clear visual story.

**What everyone is probably missing:** Visualisation as a validation tool.

**The assumption I'd challenge:** That text + tables is sufficient as a report format.

**What I'd actually do:** Build three visualisations: calibration curve, lift chart, SHAP beeswarm.

## STRONGEST POSITION: [Andrew Ng]
Andrew Ng's position was strongest because he correctly identified error analysis as the missing step everyone skipped. His pragmatic "build then study failures" approach directly addresses the gap between a working model and a reliable production system.`,

  strategy: `## [SAM ALTMAN]
**What stands out to me:** The ROI calculation at the end is underselling this. Churn models compound.

**What everyone is probably missing:** This analysis is focused on prediction, not intervention. Build an uplift model, not a churn model.

**The assumption I'd challenge:** "Month-to-month = high churn risk" — this is correlation masking a causal story.

**What I'd actually do:** Pair the churn model with a survey or NPS signal.

## [ETHAN MOLLICK]
**What stands out to me:** The human side is missing entirely. Who will use the model?

**What everyone is probably missing:** Change management. The retention team needs to trust the model.

**The assumption I'd challenge:** That the retention team will act on a churn probability score.

**What I'd actually do:** Build the model AND design the decision interface simultaneously.

## [CHRIS OLAH]
**What stands out to me:** The model is a black box. Nobody asked what representations it's learning.

**What everyone is probably missing:** Circuits-style analysis of what features activate together.

**The assumption I'd challenge:** SHAP gives you feature importance, not mechanistic understanding.

**What I'd actually do:** Build probing classifiers and activation analysis.

## [LILIAN WENG]
**What stands out to me:** The feature importance analysis is missing. We have 27 features but no ranking.

**What everyone is probably missing:** SHAP values for individual prediction explanation.

**The assumption I'd challenge:** "Top engineered feature: charge_per_tenure" — stated without evidence.

**What I'd actually do:** SHAP analysis first, then prune features to the top 12.

## [SHREYA RAJPAL]
**What stands out to me:** There are no guardrails on this model. What stops confidently wrong predictions on OOD inputs?

**What everyone is probably missing:** Model reliability engineering. Input validation, confidence thresholds, fallback logic.

**The assumption I'd challenge:** That the model will see inputs similar to its training data.

**What I'd actually do:** Add a reliability layer: input schema validation, OOD detection, low-confidence flags.

## STRONGEST POSITION: [Sam Altman]
Sam Altman's position was strongest because he reframed the entire problem: prediction without causal intervention design is incomplete. His uplift modeling direction, while requiring additional data infrastructure, addresses the fundamental limitation that a churn score alone doesn't tell you which customers will respond to retention efforts.`,
}

export const MOCK_CHAMPION_DEBATE: Record<string, string> = {
  andrej_karpathy: `**I disagree with Chip Huyen because:** Pipeline versioning and data freshness monitoring are important at scale, but for a 7K-row first model, you're gold-plating infrastructure before you know if the model is even useful. Ship the simple version, get feedback, then invest in MLOps.

**Sam Altman got something right — here's what he missed:** Uplift modeling is the correct long-term direction. But you can't build an uplift model without randomized intervention data. The pragmatic path is: ship churn model → run A/B test on retention offers → collect causal data → build uplift model v2.

**What ALL groups collectively missed:** Nobody discussed the cold start problem. New customers have no history — tenure=0, TotalCharges=0. The model will have zero signal for the customers who are actually most at risk of early churn.

**My final recommendation:** Logistic regression baseline in week 1. XGBoost with the interaction features in week 2. Deploy with a simple "call these 50 customers" workflow, not a probability API.`,

  chip_huyen: `**I disagree with Andrew Ng because:** Error analysis is important but it's a one-time exercise unless you build it into the pipeline. Systematic error analysis requires infrastructure — confusion matrix slices, automated regression testing on new data batches.

**Andrej Karpathy got something right — here's what he missed:** Starting with logistic regression is correct, but don't throw it away when you move to XGBoost. Keep it as your production fallback and interpretability baseline. Two models is better than one.

**What ALL groups collectively missed:** The monitoring gap. Everyone talked about building the model but nobody designed what happens when it starts silently degrading in production. PSI? Calibration drift? Prediction volume anomalies? These need to be dashboarded from day one.

**My final recommendation:** Build the model AND the monitoring dashboard simultaneously. Define three alerts: calibration drift > 5%, PSI > 0.15, and prediction volume change > 20%. Without these, you're flying blind after deployment.`,

  andrew_ng: `**I disagree with Sam Altman because:** Uplift modeling requires randomized controlled trial data that this team doesn't have. It's a 6-month project, not a quick win. The right sequence is: ship basic churn model → design A/B test for retention offers → collect data → build uplift model. Don't skip steps.

**Chip Huyen got something right — here's what she missed:** Pipeline versioning is critical, but the first version doesn't need Metaflow or MLflow. A Git-versioned Python package with a Makefile is production-grade enough for launch.

**What ALL groups collectively missed:** The feedback loop with the business team. Nobody proposed a regular model review with the retention team. Monthly reviews where the team shows "here's who we flagged, here's who actually churned, here's what we learned" is what builds trust and improves the model.

**My final recommendation:** Ship in 2 weeks. Logistic regression + XGBoost comparison, Lift@20% as the primary metric, SHAP explanations for the top-50 flagged customers. Then establish monthly model reviews with the retention team.`,

  sam_altman: `**I disagree with Andrej Karpathy because:** "Ship the simple version" is only good advice if you've defined what success looks like. A churn model that flags customers but doesn't lead to successful retention is a vanity metric. You need to design the intervention simultaneously.

**Andrew Ng got something right — here's what he missed:** Monthly model reviews are necessary but not sufficient. The review should include the retention team's intervention success rate, not just model accuracy. If the model correctly flags 80% of churners but the retention offer only works on 10%, the ROI is still near zero.

**What ALL groups collectively missed:** Cost-benefit framing. The churn model costs $X to build and maintain. The retention offers cost $Y per customer contacted. The expected save rate is Z%. Unless X + (Y × contacts) < Z × revenue_saved, the model is a net negative. Nobody did this math.

**My final recommendation:** Before shipping: define the retention offer, estimate its success rate from historical data, and compute the break-even point. If the math works, ship fast. If not, redesign the intervention before investing more in the model.`,
}

export const MOCK_SYNTHESIS = `## Consensus Points

- **Start simple, escalate only if needed** — supported by Theory (Karpathy), Applied (Ng), Systems (Huyen). Logistic regression baseline validates the signal; XGBoost adds complexity only when justified by measurable lift.
- **Interpretability is a prerequisite for adoption** — supported by all 4 groups. The retention team won't use a model they can't understand. SHAP explanations for individual predictions are non-negotiable.
- **Monitoring from day one, not as an afterthought** — supported by Systems (Huyen), Strategy (Rajpal), Applied (Mueller). Calibration drift, PSI, and prediction volume alerts must be built alongside the model.
- **Lift@20% over AUC** — supported by Theory (Karpathy, Raschka), Applied (Ng, Alammar). The business question is "are we calling the right 50 customers?" not "what's the overall curve shape?"

## Live Disagreements

- **Karpathy vs Altman**: Ship-fast vs design-the-intervention-first. Karpathy argues for a minimal viable model in 2 weeks; Altman argues that without a validated retention offer, the model creates no value regardless of accuracy. Both positions have merit — the resolution is to ship the model AND design the A/B test simultaneously.
- **Huyen vs Karpathy**: Monitoring infrastructure. Huyen argues dashboards and alerts from day one; Karpathy argues this is gold-plating before product-market fit. The practical middle ground: log everything, build the dashboard in sprint 2.
- **Ng vs Altman**: Uplift modeling timeline. Ng says it's a 6-month project requiring A/B data; Altman argues it's the only approach that addresses the actual business question. Both agree the first step is collecting randomized intervention data.

## Action Items (ranked by confidence)

1. **Ship logistic regression + XGBoost comparison in 2 weeks** — endorsed by 4/4 groups. Evaluate on Lift@20% and calibration curve.
2. **Add fiber+no-support+month-to-month interaction feature** — endorsed by 3/4 groups (Theory, Applied, Strategy). Likely the top predictor.
3. **Build SHAP-powered "call these 50 customers" workflow** — endorsed by 4/4 groups. This is the product, not the probability API.
4. **Deploy with 3 monitoring alerts** — endorsed by 3/4 groups. Calibration drift > 5%, PSI > 0.15, volume anomaly > 20%.
5. **Design A/B test for retention offer effectiveness** — endorsed by 3/4 groups. Required for uplift model v2.
6. **Establish monthly model review with retention team** — endorsed by 2/4 groups. Builds trust and creates feedback loop.

## The Minority Report

- **Yann LeCun** (Theory): Frame this as survival analysis (Cox PH). Nobody else agreed, but the argument that temporal structure is being discarded is technically correct. Worth a parallel experiment.
- **Chris Olah** (Strategy): Test model reasoning on synthetic edge cases. Dismissed as overkill for tabular ML, but the concrete recommendation is low-cost and high-value for catching spurious correlations.

## Bottom Line

Ship a logistic regression baseline in week 1 with the interaction feature and SHAP explanations. Evaluate on Lift@20%, not AUC. Deploy as a "call these 50 customers today" list, not a probability API. Build monitoring from day one. Then run an A/B test on retention offers to collect the causal data needed for the uplift model that Sam Altman correctly identified as the real goal.`
