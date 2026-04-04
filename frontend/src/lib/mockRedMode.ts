/**
 * Mock Red Mode data for frontend test mode.
 * Simulates a 3-round persona debate without calling any LLM API.
 * All 20 personas are included to match real Red Mode behaviour.
 */

export const MOCK_PERSONAS = [
  'andrej_karpathy', 'yann_lecun', 'sam_altman', 'geoffrey_hinton',
  'francois_chollet', 'andrew_ng', 'chip_huyen', 'jeremy_howard',
  'chris_olah', 'edward_yang',
  'ethan_mollick', 'jay_alammar', 'jonas_mueller', 'lilian_weng',
  'matei_zaharia', 'santiago_valdarrama', 'sebastian_raschka',
  'shreya_rajpal', 'tim_dettmers', 'vicki_boykis',
]

export const MOCK_ROUND1: Record<string, string> = {
  andrej_karpathy: `**What stands out to me:** The feature engineering is solid but the architecture choices feel overengineered for a 7K-row dataset.

**What everyone is probably missing:** You don't need XGBoost here. A well-regularized logistic regression with the engineered features will get you 90% of the AUC with 10% of the complexity. Ship interpretable models to stakeholders.

**The assumption I'd challenge:** "ROC-AUC is the right metric" — in deployment you pick a threshold. Track calibration and business cost, not abstract curves.

**What I'd actually do:** Run logistic regression first. If it doesn't hit 0.84 AUC, then bring in gradient boosting. Don't start with the heavy gun.`,

  yann_lecun: `**What stands out to me:** The statistical analysis is rigorous. The chi-square results on contract type are the most actionable finding here.

**What everyone is probably missing:** Nobody is thinking about the temporal structure. Churn is a survival problem, not a binary classification problem. Cox proportional hazards would dominate on this data.

**The assumption I'd challenge:** The 80/20 train-test split assumption. With only 7K rows, you're leaving performance on the table. Use full cross-validation with a proper held-out test set.

**What I'd actually do:** Frame this as survival analysis. tenure IS your time variable. Use it properly.`,

  sam_altman: `**What stands out to me:** The ROI calculation at the end — $240K revenue protection — is underselling this. Churn models compound.

**What everyone is probably missing:** This analysis is focused on prediction, not intervention. The real question is: which customers respond to retention offers? Build an uplift model, not a churn model.

**The assumption I'd challenge:** "Month-to-month = high churn risk" — this is correlation masking a causal story. These customers aren't high risk because of their contract; they're high risk because of their underlying satisfaction.

**What I'd actually do:** Pair the churn model with a survey or NPS signal to identify the actionable segment.`,

  geoffrey_hinton: `**What stands out to me:** The ethical review is perfunctory. Disparate impact on seniors (41.7% vs 23.6%) is a serious concern that deserves more than a "monitor it" recommendation.

**What everyone is probably missing:** The model will perpetuate the disparity it finds. If senior customers receive fewer retention offers because they're flagged as churners, you create a feedback loop.

**The assumption I'd challenge:** "No ethical blockers to proceed." — the SeniorCitizen disparity IS an ethical blocker unless you actively correct for it.

**What I'd actually do:** Run the model with SeniorCitizen removed. If AUC drops by more than 2%, there's an ethical problem baked into the data itself.`,

  francois_chollet: `**What stands out to me:** The feature engineering is mechanical. charge_per_tenure is a good ratio but it's the obvious one.

**What everyone is probably missing:** Interaction effects. The high-risk customer is specifically: fiber optic + no tech support + month-to-month + tenure < 12. That interaction term will be worth 5-8% AUC alone.

**The assumption I'd challenge:** XGBoost will find the interactions automatically. It won't — not with 7K rows. You need to encode the domain knowledge explicitly.

**What I'd actually do:** Create a \`high_risk_combo\` binary flag for the triple interaction. It'll be the top feature by importance.`,

  andrew_ng: `**What stands out to me:** The pipeline is well-structured and the analysis is sound. This is a good textbook churn model.

**What everyone is probably missing:** Error analysis. After training, look at which customers the model gets wrong. Those false negatives are telling you something the features can't capture.

**The assumption I'd challenge:** That 0.874 AUC is good enough. For a production churn model, I'd want to understand what the Lift curve looks like at the top 20% of scored customers.

**What I'd actually do:** Build the model, then spend equal time on error analysis and lift curve evaluation before declaring it production-ready.`,

  chip_huyen: `**What stands out to me:** Nobody talked about data freshness. When was this dataset collected? Churn patterns shift quarterly with pricing changes and competition.

**What everyone is probably missing:** The retraining cadence is wrong. "Monthly or on PSI > 0.2" — PSI is a lagging indicator. You want to retrain when business context changes.

**The assumption I'd challenge:** That sklearn Pipeline is a good serving artifact. It's fine for a demo but in production you want your preprocessing and model separately versioned.

**What I'd actually do:** Separate the feature pipeline from the model. Version them independently. Add schema validation at the prediction endpoint.`,

  jeremy_howard: `**What stands out to me:** The team jumped to XGBoost without baseline. Always start simpler.

**What everyone is probably missing:** fastai's tabular model would outperform XGBoost here with less tuning effort. Entity embeddings for categorical variables capture non-linear structure that ordinal encoding destroys.

**The assumption I'd challenge:** "OrdinalEncoder for categoricals" — this encodes Contract as {month-to-month: 0, one year: 1, two year: 2} which implies an ordering that affects the model. Use embeddings.

**What I'd actually do:** Run a fastai tabular model for 5 epochs. It'll beat XGBoost baseline by 3-4% AUC and give you better categorical representations.`,

  chris_olah: `**What stands out to me:** The model is a black box. Nobody asked what representations it's learning internally. We're flying blind on interpretability.

**What everyone is probably missing:** Circuits-style analysis: trace which features activate together to produce a high churn score. The model learns concepts — understand them before deploying.

**The assumption I'd challenge:** SHAP gives you feature importance, not mechanistic understanding. SHAP tells you what, not why. That distinction matters for debugging failures in production.

**What I'd actually do:** Build the model, then spend a week on probing classifiers and activation analysis. The insights will improve the feature engineering for v2.`,

  edward_yang: `**What stands out to me:** The whole pipeline is procedural. Nobody talked about composability or reuse. This analysis will be thrown away after the meeting.

**What everyone is probably missing:** Software engineering. Feature stores, reproducible pipelines, typed schemas. Without these, this is a one-time analysis, not a production system.

**The assumption I'd challenge:** That Jupyter notebooks are acceptable for this workload. They're not. You need a proper pipeline framework — Metaflow, Prefect, or at minimum a well-structured Python package.

**What I'd actually do:** Treat this like software. Type annotations, unit tests for each transformation, integration tests on the full pipeline. The feature engineering alone should be a tested library.`,

  ethan_mollick: `**What stands out to me:** The human side of this is missing entirely. Who will use the model? What's the workflow integration? A model nobody uses has zero ROI.

**What everyone is probably missing:** Change management. The retention team needs to trust the model. Trust is built through transparency, not accuracy. Show them the top 5 reasons for each prediction, not just a score.

**The assumption I'd challenge:** That the retention team will act on a churn probability score. They won't — not without a clear workflow and decision support interface.

**What I'd actually do:** Build the model AND design the decision interface simultaneously. Talk to the retention team before writing a line of code.`,

  jay_alammar: `**What stands out to me:** This dataset is crying out for a clear visual story. The statistical findings are buried in numbers that most stakeholders won't read.

**What everyone is probably missing:** Visualisation as a validation tool, not just presentation. Plot the distribution of churn probability scores — is it well-calibrated? Is it bimodal? The shape tells you if the model is learning signal or noise.

**The assumption I'd challenge:** That the final report format (text + tables) is sufficient. A single calibration curve and a lift chart would communicate more than 10 paragraphs.

**What I'd actually do:** Build three visualisations: calibration curve, lift chart, and SHAP beeswarm plot. These three images tell the entire story of whether the model is production-ready.`,

  jonas_mueller: `**What stands out to me:** The data quality score of 7.4/10 is treated as a minor concern. It's not. Dirty data is the primary cause of production model failures.

**What everyone is probably missing:** Automated data validation. Every feature should have a schema test — expected range, cardinality, null rate. Without this, a single upstream data change silently corrupts predictions.

**The assumption I'd challenge:** That the 11 TotalCharges nulls are the only data issue. In my experience, 7.4/10 datasets have systematic issues that only surface 3 months post-deployment.

**What I'd actually do:** Spend 20% of the project time on data validation infrastructure. It's not glamorous but it's what separates a demo from a reliable system.`,

  lilian_weng: `**What stands out to me:** The feature importance analysis is missing. We have 27 features but no ranking. Which ones actually matter?

**What everyone is probably missing:** SHAP values for individual prediction explanation. Not just for interpretability — for the business team to understand which lever to pull for each specific customer.

**The assumption I'd challenge:** "Top engineered feature: charge_per_tenure" — this is stated without evidence. Show the SHAP summary plot.

**What I'd actually do:** SHAP analysis first, then prune features to the top 12. Simpler models generalize better with 7K rows.`,

  matei_zaharia: `**What stands out to me:** The inference pipeline isn't designed for scale. Scoring one customer at a time in a FastAPI endpoint won't work if you need real-time scoring at millions of requests per day.

**What everyone is probably missing:** The operational requirements haven't been defined. Batch scoring nightly is a completely different architecture from real-time scoring at checkout. The team is designing for neither specifically.

**The assumption I'd challenge:** That FastAPI + pkl is the right serving stack. For batch jobs at scale, Spark MLlib or a feature store with online serving would be more appropriate.

**What I'd actually do:** Define the SLA first. Latency < 50ms per request? Or nightly batch of 100K customers? The answer changes the entire serving architecture.`,

  santiago_valdarrama: `**What stands out to me:** This is a well-executed analysis but it reads like it was built by someone who knows ML well and businesses less well.

**What everyone is probably missing:** The business framing. "$240K annual revenue protection" needs a confidence interval. What's the uncertainty on that estimate? Stakeholders will push back without it.

**The assumption I'd challenge:** That a churn model delivers value automatically. The value comes from the intervention, not the prediction. What's the actual retention offer? What's its success rate? Without those numbers, the ROI calculation is a fiction.

**What I'd actually do:** Build a simple decision tree first — not for production, but for stakeholder communication. Executives trust things they can draw on a whiteboard.`,

  sebastian_raschka: `**What stands out to me:** The validation methodology is the most critical piece and it's the weakest part of this analysis.

**What everyone is probably missing:** Nested cross-validation. If you tune hyperparameters on the CV folds and report CV performance, you're optimistically biased. The reported 0.874 AUC is likely 3-5% inflated.

**The assumption I'd challenge:** "80 Optuna trials is sufficient." With this search space size and only 5-fold CV, the variance in each trial's estimate is too high for reliable selection.

**What I'd actually do:** Nested 5×10 CV (outer 5-fold, inner 10-fold for tuning). It takes longer but the reported performance will actually be reproducible.`,

  shreya_rajpal: `**What stands out to me:** There are no guardrails on this model. Once it's deployed, what stops it from making confidently wrong predictions on out-of-distribution inputs?

**What everyone is probably missing:** Model reliability engineering. Input validation, output confidence thresholds, fallback logic. A churn model that scores a customer who's been with the company for 200 months (impossible) should flag that, not silently score it.

**The assumption I'd challenge:** That the model will see inputs similar to its training data. It won't — not after 6 months of product changes, pricing updates, or customer segment shifts.

**What I'd actually do:** Add a reliability layer: input schema validation, out-of-distribution detection, and a "low confidence" flag on predictions below a threshold. These aren't optional in production.`,

  tim_dettmers: `**What stands out to me:** Nobody talked about the compute budget. How long does training + tuning actually take? 80 Optuna trials × 5-fold CV is potentially hours of compute.

**What everyone is probably missing:** Quantization-aware training and efficient inference. Even for tabular models, model compression matters at scale. A quantized model can be 4× faster at inference with minimal accuracy loss.

**The assumption I'd challenge:** That GPU acceleration isn't relevant for tabular ML. XGBoost-GPU can be 10× faster on large hyperparameter search spaces. Use it.

**What I'd actually do:** Profile the tuning pipeline first. If it takes more than 30 minutes, switch to GPU-accelerated XGBoost and use early stopping aggressively to prune bad trials in the first few rounds.`,

  vicki_boykis: `**What stands out to me:** This analysis assumes the data is correct. It isn't — it never is. Someone in engineering changed a column name and nobody noticed.

**What everyone is probably missing:** Data provenance. Where did this CSV come from? Who owns it? When was it last updated? Is this a training snapshot or a live export? These questions determine whether the model is valid or completely wrong.

**The assumption I'd challenge:** That a CSV file is a reliable data source for a production ML system. It's not. You need a data contract with the upstream team and automated tests that run on every new data delivery.

**What I'd actually do:** Before touching a model, I'd spend a day documenting the data lineage. Who produces it, what schema it should have, and what monitoring exists to catch upstream changes. Everything else is secondary.`,
}

export const MOCK_ROUND2: Record<string, string> = {
  andrej_karpathy: `**I disagree with Yann because:** Survival analysis is theoretically beautiful but practically wrong here. Cox PH assumes proportional hazards — you'd need to verify that before using it. Gradient boosting with tenure as a feature IS using the temporal information, just not explicitly.

**Geoffrey got something right — here's what they missed:** The ethical concern about SeniorCitizen is valid, but the solution isn't removing the feature — it's applying fairness constraints during optimization. Equalized odds post-hoc correction is better than throwing away signal.

**What nobody said that should have been said:** The business hasn't defined their retention offer budget. Without a cost matrix, every metric choice is arbitrary. Get the cost-benefit numbers before picking AUC vs F2 vs anything else.`,

  yann_lecun: `**I disagree with Sam because:** Uplift modeling requires randomized intervention data. You can't do uplift from observational churn data without strong assumptions. Sam's recommendation presupposes infrastructure this team doesn't have.

**Andrej got something right — here's what they missed:** Interpretability is real, but for 7K rows logistic regression won't find the interaction effects that François identified. You need at least a shallow tree ensemble to capture them without manual encoding.

**What nobody said that should have been said:** Temporal leakage. If the training data includes customers who churned BECAUSE of a price change that happened after the feature snapshot, your model is learning noise.`,

  sam_altman: `**I disagree with Geoffrey because:** Removing SeniorCitizen because it shows disparity is the wrong intervention. You're hiding a real signal from the model AND potentially making worse decisions about seniors as a result.

**Chip got something right — here's what they missed:** Data freshness matters, but the more urgent problem is selection bias in the training set. Which customers were OFFERED retention deals before they churned? If retention was applied non-randomly, the training labels are contaminated.

**What nobody said that should have been said:** This model should be the starting point of a conversation with product, not the end. The features that drive churn tell you what to fix in the product.`,

  geoffrey_hinton: `**I disagree with Andrej because:** "Well-regularized logistic regression" won't capture the interaction effects François correctly identified. The high-risk combination (fiber + no support + month-to-month) is multiplicative, not additive.

**Sebastian got something right — here's what they missed:** Nested CV is critical, but it understates the problem. The bigger bias is that hyperparameter tuning changes the model — reporting the tuned model's CV score is optimistically biased regardless of nesting.

**What nobody said that should have been said:** The model assumes the future looks like the past. If the company changes its pricing strategy in response to these predictions, the predictions become invalid. This is Goodhart's Law applied to churn models.`,

  francois_chollet: `**I disagree with Jeremy because:** fastai tabular with entity embeddings needs more data than 7K rows to learn meaningful embeddings for low-cardinality categorical variables. You'll overfit.

**Lilian got something right — here's what they missed:** SHAP analysis is good but the real value is SHAP interaction values, not just main effects. The interaction between contract type and tenure is the story this dataset is telling.

**What nobody said that should have been said:** All of us are assuming the goal is AUC maximization. The business question might be "retain the top 200 at-risk customers" — in which case Precision@200 is the only metric that matters.`,

  andrew_ng: `**I disagree with Sam because:** Uplift modeling is the right long-term direction but it requires data you don't have yet. Build the churn model now, run an A/B test on retention offers, then build the uplift model. Don't skip steps.

**François got something right — here's what they missed:** The interaction feature idea is good, but domain expertise should drive feature creation, not trial-and-error. Talk to the customer success team before encoding assumptions.

**What nobody said that should have been said:** Model interpretability for the business team is not optional. If the retention team can't understand why a customer was flagged, they won't trust the model and won't use it.`,

  chip_huyen: `**I disagree with Jeremy because:** The serving infrastructure question is more important than the model choice. A fastai tabular model with entity embeddings is harder to serve and explain than XGBoost with SHAP.

**Andrew got something right — here's what they missed:** Error analysis needs to be systematic, not anecdotal. Build a confusion matrix slice analysis: where does the model fail? New customers? High-paying customers? Specific contract types?

**What nobody said that should have been said:** Monitoring in production is where most churn models die. The PSI threshold of 0.2 is arbitrary. You need to calibrate the retraining trigger against your specific data distribution.`,

  jeremy_howard: `**I disagree with Sebastian because:** A holdout set with 1,400 rows (20% of 7K) will have high variance in AUC estimates. Nested CV gives you more reliable estimates of generalization. The computational cost is worth it.

**Chip got something right — here's what they missed:** Schema validation at the prediction endpoint is essential, but you also need to handle covariate shift gracefully — log anomalous inputs, don't silently score them.

**What nobody said that should have been said:** The whole team focused on AUC. Nobody asked: what's the model latency requirement? If this needs to score 100K customers overnight in batch, all the serving advice changes.`,

  chris_olah: `**I disagree with Lilian because:** SHAP is a post-hoc attribution method. It tells you the model's reasoning on average, not the actual computational mechanism. For debugging production failures, you need mechanistic understanding, not attribution scores.

**Edward got something right — here's what they missed:** Software engineering discipline is important, but before you build a typed schema, you need to understand what the model is actually computing. I've seen well-engineered systems ship confidently wrong models because nobody looked inside.

**What nobody said that should have been said:** Test the model's reasoning on synthetic edge cases. Create customers with known churn risk and verify the model's predictions match intuition. If they don't, the model learned something spurious.`,

  edward_yang: `**I disagree with Ethan because:** Change management and human factors matter, but they're downstream of having a reliable system. A buggy model with great UX is worse than a good model with a clunky interface. Get the engineering right first.

**Chip got something right — here's what they missed:** Separate versioning of feature pipeline and model is correct but incomplete. You also need to version the data schema. If the upstream team adds a column, your pipeline should validate it, not silently consume it.

**What nobody said that should have been said:** Reproducibility. Can you re-run this experiment from scratch and get the same result? If not, this isn't a production-ready analysis — it's a one-time experiment. Set random seeds, pin library versions, log everything.`,

  ethan_mollick: `**I disagree with Sam because:** Uplift models require A/B test data and significant infrastructure. For most teams, starting with a simple churn score and building the feedback loop manually is more practical and faster to value.

**Jay got something right — here's what they missed:** Visualisations aren't just for stakeholders. The calibration curve is diagnostic — if it's badly miscalibrated, the model's probability scores are meaningless for threshold selection. Build it before any business presentation.

**What nobody said that should have been said:** Pilot programs. Don't roll out to all customers at once. Run a 30-day pilot with 10% of high-risk customers, measure actual retention rate improvement, then scale. The ROI estimate becomes real data.`,

  jay_alammar: `**I disagree with Chris because:** Mechanistic interpretability at the circuits level is appropriate for deep learning models with billions of parameters. For XGBoost on 27 features, SHAP is sufficient and far more actionable.

**Jonas got something right — here's what they missed:** Data validation infrastructure is critical, but it needs to be visual too. A data quality dashboard that shows schema drift and value distribution changes over time is worth 10× more than automated tests alone.

**What nobody said that should have been said:** The model card. Document who the model was built for, what data it was trained on, known failure modes, and ethical considerations. This should be mandatory before any production deployment.`,

  jonas_mueller: `**I disagree with Edward because:** Typed schemas and software engineering are important, but they're cargo-culting if the underlying data quality issues aren't addressed. You can have perfectly typed code reading garbage data.

**Shreya got something right — here's what they missed:** Out-of-distribution detection is necessary, but the threshold for "OOD" needs to be calibrated against historical data distribution. What counts as an anomalous tenure value if the product changes its pricing and attracts a new customer segment?

**What nobody said that should have been said:** Data contracts with the upstream engineering team. Not as a document but as an automated test that runs on every data delivery and pages someone when it fails. That's the only data quality mechanism that actually works.`,

  lilian_weng: `**I disagree with Andrej because:** Starting with logistic regression is sensible as a sanity check, but with charge_per_tenure and contract_risk as engineered features, you already have nonlinearity baked in. XGBoost won't hurt.

**Geoffrey got something right — here's what they missed:** The feedback loop concern is valid and underappreciated. If the model scores seniors poorly and they receive fewer retention offers, you collect less data on retained seniors, which makes future models worse.

**What nobody said that should have been said:** Feature importance from tree models is unreliable for correlated features. MonthlyCharges and TotalCharges are highly correlated — their importances will be split arbitrarily between them.`,

  matei_zaharia: `**I disagree with Edward because:** Metaflow and Prefect are great for ML pipelines, but for a 7K-row tabular dataset, they're serious overkill. The simplest tool that works is the right tool. Over-engineering the pipeline is as bad as under-engineering it.

**Chip got something right — here's what they missed:** Define the SLA before the architecture. Once you know whether this is batch or real-time, the right infrastructure choice is obvious. Don't design for both simultaneously — you'll get something that does neither well.

**What nobody said that should have been said:** Graceful degradation. What does the system do when the model service is down? Fall back to a rule-based system (high tenure + month-to-month = high risk). The rule-based fallback is often 80% as accurate as the model and 100% more reliable.`,

  santiago_valdarrama: `**I disagree with Vicki because:** Data provenance documentation is important but it can't be the blocker. In most organisations, you'll never get a perfect data contract. Build the model with what you have, document the assumptions, and iterate.

**Ethan got something right — here's what they missed:** The decision interface design is critical, but frame it differently. The retention team doesn't need a probability score — they need a ranked list of "call these 50 customers today." That's a product decision masquerading as a modelling decision.

**What nobody said that should have been said:** Sensitivity analysis. What happens to model performance if the churn rate changes from 26% to 35% next quarter? If the model breaks under realistic distribution shifts, it's not production-ready.`,

  sebastian_raschka: `**I disagree with Jeremy because:** A holdout set with 1,400 rows (20% of 7K) will have high variance in AUC estimates. Nested CV gives you more reliable estimates of generalization. The computational cost is worth it.

**Andrew got something right — here's what they missed:** Lift curve analysis is the correct frame for business impact. But go further: calibrate the model and report reliability diagrams. If a customer scores 0.7 churn probability, does 70% of that segment actually churn?

**What nobody said that should have been said:** Statistical significance of the AUC difference between models. If XGBoost beats logistic regression by 0.03 AUC, is that difference real or sampling noise? Run McNemar's test on the predictions.`,

  shreya_rajpal: `**I disagree with Jonas because:** Data contracts are important, but reliability engineering at the model boundary is more urgent. A bad upstream data change will cause loud failures that someone will notice. A model that silently produces wrong outputs for OOD inputs is far more dangerous.

**Tim got something right — here's what they missed:** Compute efficiency matters, but so does inference reliability. A quantized model that's 4× faster but has a 2% accuracy drop needs to be validated against the original before deployment, not assumed equivalent.

**What nobody said that should have been said:** Rollback strategy. What's the plan when the model performs worse in production than in validation? You need a versioned model registry and the ability to instantly revert to the previous version. Nobody builds this until they need it — then it's too late.`,

  tim_dettmers: `**I disagree with Santiago because:** You can't do sensitivity analysis in the abstract. You need to simulate it. Generate synthetic data with shifted distributions and measure model degradation. "What if churn rate changes to 35%" needs to be a concrete experiment, not a question.

**Matei got something right — here's what they missed:** Graceful degradation to a rule-based fallback is the right engineering instinct. But the fallback rule should be trained from data too — a simple decision tree with depth 3 gives you an interpretable, deployable backup that's not just a guess.

**What nobody said that should have been said:** Memory bandwidth is the bottleneck in tabular inference, not compute. A model that fits in L2 cache will score 10× faster than one that doesn't. For 100K customer batch scoring, model size matters.`,

  vicki_boykis: `**I disagree with Edward because:** Perfect reproducibility is the enemy of shipping. Random seeds and pinned library versions are good practice but in a business context you need to balance engineering rigour with velocity. Build the reproducibility infrastructure incrementally.

**Jonas got something right — here's what they missed:** Data contracts as automated tests are exactly right, but they need to cover semantic correctness, not just schema. A contract that checks "TotalCharges is a float" won't catch the case where upstream silently starts filling nulls with -1 instead of NaN.

**What nobody said that should have been said:** The most dangerous part of this whole pipeline isn't the model — it's the feature engineering code. It runs in production on every prediction. One off-by-one error in charge_per_tenure silently degrades every prediction forever. That code needs more tests than the model.`,
}

export const MOCK_SYNTHESIS = `## Consensus Points

- **Feature engineering beats raw features** — supported by Karpathy, LeCun, Ng, Weng, Chollet, Alammar. The engineered features (charge_per_tenure, contract_risk, is_new_customer) capture domain knowledge that raw columns miss.
- **Interpretability is non-negotiable for adoption** — supported by Karpathy, Ng, Huyen, Howard, Mollick. The model must be explainable to the retention team or it won't be used.
- **AUC alone is insufficient** — supported by Chollet, Raschka, Howard, Alammar. Lift curve, calibration, and business cost must be evaluated before declaring the model production-ready.
- **Production reliability requires explicit engineering** — supported by Huyen, Yang, Rajpal, Mueller, Boykis. Schema validation, data contracts, OOD detection, and rollback strategy are non-optional.
- **Monitoring and retraining cadence must be calibrated, not assumed** — supported by Huyen, Hinton, Ng, Zaharia. PSI > 0.2 is an arbitrary threshold; calibrate against your specific data distribution.

## Live Disagreements

- **LeCun vs Karpathy**: Survival analysis (Cox PH) vs standard binary classification. LeCun argues tenure is a time variable that should be modeled explicitly; Karpathy argues gradient boosting with tenure as a feature captures this without the Cox PH assumptions.
- **Hinton vs Altman**: Whether to remove SeniorCitizen. Hinton argues the 41.7% vs 23.6% disparity is an ethical blocker; Altman argues removing it hides signal and leads to worse decisions for seniors.
- **Raschka vs Howard**: Nested CV vs holdout set. Raschka argues 1,400-row holdout has too much variance; Howard argues nested CV overhead isn't worth it at this scale.
- **Olah vs Weng**: SHAP attribution vs mechanistic understanding. Olah argues SHAP doesn't reveal what the model actually computes; Weng argues SHAP is sufficient and far more actionable for tabular models.
- **Zaharia vs Yang**: Pipeline infrastructure scope. Zaharia argues Metaflow/Prefect is overkill for 7K rows; Yang argues software discipline is non-negotiable regardless of data size.

## Action Items (ranked by confidence)

1. **Ship logistic regression baseline first** — endorsed by 9 experts. Provides interpretable benchmark, reveals whether complexity is actually needed.
2. **SHAP analysis on the final model** — endorsed by 8 experts. Required for feature importance, error analysis, and retention team trust.
3. **Evaluate Lift@20% and calibration curve** — endorsed by 7 experts. AUC does not tell you where to set the decision threshold.
4. **Add fiber+no-support+month-to-month interaction feature** — endorsed by 6 experts (Chollet, Hinton, LeCun, Ng, Weng, Alammar). Likely top predictor.
5. **Input schema validation + OOD detection at prediction endpoint** — endorsed by 6 experts. Non-optional for production.
6. **Data contract with upstream engineering team** — endorsed by 5 experts. Automated tests that page someone when schema changes.
7. **Define SLA before finalising serving architecture** — endorsed by 4 experts. Batch vs real-time changes everything about the infrastructure.

## The Minority Report

- **LeCun**: Frame this as survival analysis (Cox PH). Nobody else agreed, but the argument that temporal structure is being discarded is technically correct. Worth a parallel experiment before final model selection.
- **Altman**: Build an uplift model, not a churn model. Requires A/B test data the team doesn't have, but the underlying point — that prediction without causal intervention design is incomplete — should shape the v2 roadmap.
- **Olah**: Mechanistic interpretability beyond SHAP. Dismissed as overkill for tabular ML, but testing the model on synthetic edge cases (his concrete recommendation) is low-cost and high-value.

## Bottom Line

Train logistic regression and XGBoost in parallel (1 day). Evaluate both on Lift@20%, calibration, and McNemar's significance test — not just AUC. Before deployment: address the SeniorCitizen disparity explicitly, add input validation and OOD flagging, and define what "the model is wrong" looks like and how to roll back. The 20 experts agree on the model; they disagree on the infrastructure. Invest in the infrastructure — it's what determines whether this creates value in 6 months or gets quietly abandoned.`
