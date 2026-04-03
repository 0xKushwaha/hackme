/**
 * Mock pipeline data for frontend test mode.
 * Simulates realistic agent outputs without calling any LLM API.
 */

export interface MockStep {
  agent: string
  lines: string[]
  durationMs: number
}

export const MOCK_STEPS: MockStep[] = [
  {
    agent: 'explorer',
    durationMs: 2200,
    lines: [
      '⚡ [AGENT:explorer]',
      '[Explorer] Scanning dataset structure...',
      '[Explorer] Found 1,247 rows × 23 columns.',
      '[Explorer] Target column detected: "churn" (binary, 0/1).',
      '[Explorer] Key numeric features: tenure (0–72 months), MonthlyCharges ($18–$118), TotalCharges.',
      '[Explorer] Categorical features: Contract, PaymentMethod, InternetService, TechSupport (7 total).',
      '[Explorer] Class distribution: 73.5% no-churn, 26.5% churn — moderate imbalance.',
      '[Explorer] Missing values: TotalCharges has 11 nulls (new customers, tenure=0).',
      '[Explorer] High correlation: MonthlyCharges ↔ TotalCharges (r=0.83). Potential multicollinearity.',
      '✅ [AGENT_DONE:explorer]',
    ],
  },
  {
    agent: 'skeptic',
    durationMs: 1800,
    lines: [
      '⚡ [AGENT:skeptic]',
      '[Skeptic] Challenging dataset assumptions...',
      '[Skeptic] ⚠ TotalCharges nulls are systematic (tenure=0), safe to fill with 0.0.',
      '[Skeptic] ⚠ SeniorCitizen encoded as int (0/1) while all other categoricals are strings — inconsistent.',
      '[Skeptic] ⚠ Leakage risk: TotalCharges ≈ tenure × MonthlyCharges. Recommend dropping or engineering carefully.',
      '[Skeptic] ⚠ No true duplicates found, but 3 rows have identical feature vectors with different labels.',
      '[Skeptic] Data quality score: 7.4 / 10. Proceed with caution on TotalCharges.',
      '✅ [AGENT_DONE:skeptic]',
    ],
  },
  {
    agent: 'statistician',
    durationMs: 2500,
    lines: [
      '⚡ [AGENT:statistician]',
      '[Statistician] Running statistical analysis...',
      '[Statistician] Churn rate: 26.5% (1,869 / 7,043 customers).',
      '[Statistician] ANOVA — tenure vs churn: F=892.4, p<0.001 ✓',
      '[Statistician] ANOVA — MonthlyCharges vs churn: F=640.1, p<0.001 ✓',
      '[Statistician] Chi-square — Contract type vs churn: χ²=1184.9, p<0.001 ✓',
      '[Statistician] Month-to-month customers churn 3.6× more than two-year contract holders.',
      '[Statistician] Mean tenure: churned=18.4 months, retained=37.6 months.',
      '[Statistician] MonthlyCharges bimodal: DSL cluster ~$45, Fiber optic cluster ~$82.',
      '✅ [AGENT_DONE:statistician]',
    ],
  },
  {
    agent: 'ethicist',
    durationMs: 1400,
    lines: [
      '⚡ [AGENT:ethicist]',
      '[Ethicist] Reviewing dataset for ethical concerns...',
      '[Ethicist] No direct protected attributes (race, religion, national origin) present.',
      '[Ethicist] SeniorCitizen (binary) may proxy for age — monitor fairness across this group.',
      '[Ethicist] Gender present — check precision/recall parity: Male vs Female.',
      '[Ethicist] Recommend: track disparate impact ratio (80% rule) on SeniorCitizen and gender.',
      '[Ethicist] No significant ethical blockers. Proceed with fairness monitoring in place.',
      '✅ [AGENT_DONE:ethicist]',
    ],
  },
  {
    agent: 'feature_engineer',
    durationMs: 2000,
    lines: [
      '⚡ [AGENT:feature_engineer]',
      '[FeatureEng] Engineering predictive features...',
      '[FeatureEng] + charge_per_tenure = MonthlyCharges / max(tenure, 1)',
      '[FeatureEng] + is_new_customer = (tenure < 6).astype(int)',
      '[FeatureEng] + contract_risk = {month-to-month: 3, one year: 2, two year: 1}',
      '[FeatureEng] + service_count = sum of 6 optional service columns',
      '[FeatureEng] + has_no_support = (TechSupport == "No") & (InternetService != "No")',
      '[FeatureEng] DROP: TotalCharges (leakage). ENCODE: 7 object columns via OrdinalEncoder.',
      '[FeatureEng] SCALE: StandardScaler on all numeric features.',
      '[FeatureEng] Final feature set: 27 columns.',
      '✅ [AGENT_DONE:feature_engineer]',
    ],
  },
  {
    agent: 'pragmatist',
    durationMs: 1900,
    lines: [
      '⚡ [AGENT:pragmatist]',
      '[Pragmatist] Building action plan...',
      '[Pragmatist] Primary model: XGBoost — handles mixed types, robust to outliers, fast.',
      '[Pragmatist] Baseline model: Logistic Regression for interpretability benchmark.',
      '[Pragmatist] Evaluation metric: ROC-AUC (handles 26.5% class imbalance better than accuracy).',
      '[Pragmatist] Split: 80/20 stratified. Cross-validation: 5-fold stratified CV.',
      '[Pragmatist] Expected baseline AUC: ~0.82. Target: >0.88.',
      '[Pragmatist] Timeline: feature prep (1h) → training (30m) → tuning (2h) → evaluation (30m).',
      '✅ [AGENT_DONE:pragmatist]',
    ],
  },
  {
    agent: 'devil_advocate',
    durationMs: 1600,
    lines: [
      '⚡ [AGENT:devil_advocate]',
      '[DevilAdv] Stress-testing the plan...',
      '[DevilAdv] ✗ XGBoost may overfit: only 1.2K samples after split. Consider LightGBM or simpler model.',
      '[DevilAdv] ✗ ROC-AUC obscures calibration — business cost of FN ≠ FP. Use Precision-Recall AUC.',
      '[DevilAdv] ✗ 5-fold CV on 1K rows = 200-sample folds. High variance in estimates.',
      '[DevilAdv] Counter-proposal: CatBoost with native categorical handling + SMOTE for imbalance.',
      '[DevilAdv] Alternative metric: F2-score (weights recall 2× — missing a churner costs more).',
      '✅ [AGENT_DONE:devil_advocate]',
    ],
  },
  {
    agent: 'optimizer',
    durationMs: 2100,
    lines: [
      '⚡ [AGENT:optimizer]',
      '[Optimizer] Designing hyperparameter strategy...',
      '[Optimizer] Search space: n_estimators [100,200,300], max_depth [3,4,5], lr [0.01,0.05,0.1].',
      '[Optimizer] subsample [0.7,0.8,1.0], colsample_bytree [0.7,0.9,1.0], scale_pos_weight=2.77.',
      '[Optimizer] Method: Optuna TPE sampler, 80 trials, 5-fold CV per trial.',
      '[Optimizer] Early stopping: 15 rounds. Pruner: MedianPruner.',
      '[Optimizer] Estimated optimal config: depth=4, lr=0.05, n_est=200, subsample=0.8.',
      '[Optimizer] Projected AUC: 0.874 ± 0.018 (cross-val).',
      '✅ [AGENT_DONE:optimizer]',
    ],
  },
  {
    agent: 'architect',
    durationMs: 1700,
    lines: [
      '⚡ [AGENT:architect]',
      '[Architect] Designing system architecture...',
      '[Architect] Training pipeline: sklearn Pipeline → [Imputer → OrdinalEncoder → Scaler → XGBClassifier].',
      '[Architect] Serving: FastAPI /predict endpoint. Latency target: P95 < 50ms.',
      '[Architect] Artifact storage: model.pkl + feature_metadata.json + thresholds.json.',
      '[Architect] Monitoring: PSI on input features (retrain if PSI > 0.2).',
      '[Architect] Drift detection: track daily churn rate; alert if delta > 3% vs baseline.',
      '[Architect] Batch scoring: pandas apply on customer table, results to PostgreSQL churn_scores.',
      '✅ [AGENT_DONE:architect]',
    ],
  },
  {
    agent: 'storyteller',
    durationMs: 2400,
    lines: [
      '⚡ [AGENT:storyteller]',
      '[Storyteller] Synthesising final narrative...',
      '[Storyteller] ═══════════════════════════════════════════════════════',
      '[Storyteller] EXECUTIVE SUMMARY',
      '[Storyteller] ═══════════════════════════════════════════════════════',
      '[Storyteller] This telecom dataset reveals a clear churn risk pattern.',
      '[Storyteller] Customers on month-to-month contracts with high charges',
      '[Storyteller] and low tenure are 3.6× more likely to churn.',
      '[Storyteller] Our XGBoost model achieves 0.874 ROC-AUC, identifying',
      '[Storyteller] 78% of churners before they leave.',
      '[Storyteller] TOP 3 ACTIONABLE RECOMMENDATIONS:',
      '[Storyteller] 1. Offer contract upgrades at the 6-month mark.',
      '[Storyteller] 2. Target fiber optic customers paying >$80/mo.',
      '[Storyteller] 3. Flag tenure<12 + no add-ons for proactive outreach.',
      '[Storyteller] Estimated retention uplift: 12–18% of at-risk segment.',
      '✅ [AGENT_DONE:storyteller]',
    ],
  },
]

export interface MockEntry {
  agent: string
  role: string
  content: string
  metadata: Record<string, unknown>
}

export const MOCK_RESULT_ENTRIES: MockEntry[] = [
  {
    agent: 'explorer', role: 'analysis', metadata: {},
    content: `## Dataset Overview

**Shape:** 7,043 rows × 23 columns
**Target:** \`Churn\` (binary: Yes / No)
**Class balance:** 73.5% No-churn · 26.5% Churn

### Key Features Identified
| Feature | Type | Notes |
|---|---|---|
| tenure | numeric | 0–72 months, strong churn signal |
| MonthlyCharges | numeric | $18–$118, bimodal distribution |
| Contract | categorical | Month-to-month = highest churn risk |
| TechSupport | categorical | "No" correlates with churn |
| TotalCharges | numeric | ⚠ Near-leakage — correlates with tenure × charges |

### Missing Values
- \`TotalCharges\`: 11 nulls — all have \`tenure = 0\` (new customers). Safe to fill with 0.

### Correlations
- MonthlyCharges ↔ TotalCharges: r = 0.83 (high multicollinearity)
- tenure ↔ Churn: r = −0.35 (longer tenure → lower churn)`,
  },
  {
    agent: 'skeptic', role: 'analysis', metadata: {},
    content: `## Data Quality Assessment  **Score: 7.4 / 10**

### Issues Found

**🔴 High Priority**
- \`TotalCharges\` ≈ \`tenure × MonthlyCharges\` — near-perfect leakage if included naively. Recommend drop or engineer ratio carefully.

**🟡 Medium Priority**
- \`SeniorCitizen\` encoded as int (0/1) while all other categoricals are strings — inconsistent encoding pipeline.
- 3 rows have identical feature vectors but different labels. Possible data entry error.

**🟢 Low Priority**
- No true duplicates found (7,043 unique CustomerIDs).
- 11 TotalCharges nulls are explainable and systematic — not random missingness.

### Recommendation
Drop \`TotalCharges\`, fix \`SeniorCitizen\` encoding, proceed with cleaned dataset.`,
  },
  {
    agent: 'statistician', role: 'analysis', metadata: {},
    content: `## Statistical Analysis

### Churn Rate
Overall churn: **26.54%** (1,869 / 7,043 customers)

### Hypothesis Tests
| Feature | Test | Statistic | p-value | Significant |
|---|---|---|---|---|
| tenure | ANOVA | F = 892.4 | < 0.001 | ✓ |
| MonthlyCharges | ANOVA | F = 640.1 | < 0.001 | ✓ |
| Contract type | Chi-square | χ² = 1184.9 | < 0.001 | ✓ |
| TechSupport | Chi-square | χ² = 823.1 | < 0.001 | ✓ |
| SeniorCitizen | Chi-square | χ² = 159.2 | < 0.001 | ✓ |

### Key Findings
- **Month-to-month** contract customers churn **3.6×** more than two-year contract holders.
- Mean tenure: churned = **18.4 months** vs retained = **37.6 months**.
- Fiber optic customers have the highest churn rate at **41.9%**.
- MonthlyCharges distribution is bimodal: DSL cluster ~$45, Fiber cluster ~$82.`,
  },
  {
    agent: 'ethicist', role: 'analysis', metadata: {},
    content: `## Ethical Review

### Protected Attributes
No directly sensitive attributes (race, religion, national origin) are present.

### Fairness Concerns
| Attribute | Concern | Recommendation |
|---|---|---|
| SeniorCitizen | Age proxy — seniors may be disproportionately flagged | Track precision/recall parity across groups |
| gender | Direct attribute present | Monitor disparate impact ratio (80% rule) |

### Disparate Impact Analysis (Pre-model)
- Female churn rate: 25.2% · Male churn rate: 26.2% — minimal raw difference.
- SeniorCitizen churn rate: 41.7% vs 23.6% for non-seniors — **significant gap**, monitor closely.

### Verdict
No ethical blockers to proceed. Recommend fairness monitoring dashboard tracking precision/recall parity across \`SeniorCitizen\` and \`gender\` groups post-deployment.`,
  },
  {
    agent: 'feature_engineer', role: 'analysis', metadata: {},
    content: `## Feature Engineering Plan

### New Features
\`\`\`python
# Ratio feature — captures value efficiency
df['charge_per_tenure'] = df['MonthlyCharges'] / df['tenure'].clip(lower=1)

# Lifecycle flag
df['is_new_customer'] = (df['tenure'] < 6).astype(int)

# Ordinal contract risk score
contract_map = {'Month-to-month': 3, 'One year': 2, 'Two year': 1}
df['contract_risk'] = df['Contract'].map(contract_map)

# Service adoption count
service_cols = ['PhoneService','MultipleLines','OnlineSecurity',
                'OnlineBackup','DeviceProtection','TechSupport']
df['service_count'] = df[service_cols].apply(lambda x: (x == 'Yes').sum(), axis=1)

# Vulnerability flag
df['has_no_support'] = ((df['TechSupport'] == 'No') &
                         (df['InternetService'] != 'No')).astype(int)
\`\`\`

### Dropped Features
- \`TotalCharges\` — leakage risk
- \`CustomerID\` — identifier, no signal

### Encoding & Scaling
- OrdinalEncoder on 7 remaining categorical columns
- StandardScaler on all numeric features
- **Final feature count: 27 columns**`,
  },
  {
    agent: 'pragmatist', role: 'plan', metadata: {},
    content: `## Modeling Plan

### Selected Models
1. **XGBoost** (primary) — handles mixed types, robust to outliers, fast inference
2. **Logistic Regression** (baseline) — interpretable, quick sanity check

### Evaluation Strategy
- **Primary metric:** ROC-AUC (robust to 26.5% class imbalance)
- **Secondary:** Precision-Recall AUC, F2-score (weights recall 2×)
- **Split:** 80/20 stratified train-test
- **Validation:** 5-fold stratified cross-validation

### Success Criteria
| Model | Target AUC | Acceptable |
|---|---|---|
| Logistic Regression baseline | ≥ 0.78 | ≥ 0.74 |
| XGBoost | ≥ 0.88 | ≥ 0.84 |

### Timeline
Data prep → 1h · Training → 30m · Tuning → 2h · Evaluation → 30m`,
  },
  {
    agent: 'devil_advocate', role: 'plan', metadata: {},
    content: `## Critical Challenges to the Plan

### ✗ Model Choice
XGBoost may overfit with only ~1,000 training samples after split. Consider LightGBM (faster, less prone to overfitting on small data) or even a well-tuned Random Forest.

### ✗ Metric Framing
ROC-AUC hides calibration. In churn, the cost of a **false negative** (missed churner) greatly exceeds a **false positive** (unnecessary retention offer). Recommend **Precision-Recall AUC** or **F2-score** as primary.

### ✗ Validation Variance
5-fold CV on ~1,000 rows = 200 samples per fold. Metric variance will be high. Consider repeated 10-fold CV (10× 10-fold) for more stable estimates.

### Counter-Proposal
Use **CatBoost** with native categorical handling (eliminates manual encoding step) + **SMOTE** oversampling on training folds only (prevents data leakage in CV).`,
  },
  {
    agent: 'optimizer', role: 'plan', metadata: {},
    content: `## Hyperparameter Optimization Strategy

### Search Space (XGBoost)
\`\`\`python
param_space = {
    'n_estimators':      [100, 200, 300],
    'max_depth':         [3, 4, 5],
    'learning_rate':     [0.01, 0.05, 0.1],
    'subsample':         [0.7, 0.8, 1.0],
    'colsample_bytree':  [0.7, 0.9, 1.0],
    'scale_pos_weight':  [2.77],   # ratio of negatives/positives
    'min_child_weight':  [1, 3, 5],
}
\`\`\`

### Optimization Method
- **Framework:** Optuna with TPE (Tree-structured Parzen Estimator) sampler
- **Trials:** 80 (budget-aware)
- **CV:** 5-fold stratified per trial
- **Early stopping:** 15 rounds
- **Pruner:** MedianPruner (kills unpromising trials early)

### Projected Results
| Config | CV AUC | Std |
|---|---|---|
| Baseline (default XGB) | 0.841 | ±0.024 |
| Optimised | **0.874** | ±0.018 |

**Estimated optimal:** depth=4, lr=0.05, n\_est=200, subsample=0.8`,
  },
  {
    agent: 'architect', role: 'plan', metadata: {},
    content: `## System Architecture

### Training Pipeline
\`\`\`
Raw CSV
  └─ SimpleImputer (fill TotalCharges nulls → 0)
  └─ FeatureEngineer (custom transformer)
  └─ OrdinalEncoder (7 categorical cols)
  └─ StandardScaler (numeric features)
  └─ XGBClassifier (optimised params)
\`\`\`
Wrapped in \`sklearn.Pipeline\` for reproducibility.

### Serving
- **API:** FastAPI \`/predict\` endpoint
- **Latency target:** P95 < 50ms
- **Batch scoring:** Pandas apply on full customer table → PostgreSQL \`churn_scores\`

### Artifacts
\`\`\`
experiments/
  model.pkl              # trained pipeline
  feature_metadata.json  # column names, dtypes, expected ranges
  thresholds.json        # decision threshold (default 0.5, tunable)
  optuna_study.pkl       # reproducible tuning history
\`\`\`

### Monitoring
- **Input drift:** PSI on numeric features — retrain trigger: PSI > 0.2
- **Output drift:** daily churn rate delta — alert if Δ > 3% vs 30-day baseline
- **Retraining cadence:** monthly or on drift alert`,
  },
  {
    agent: 'storyteller', role: 'narrative', metadata: {},
    content: `## Executive Summary

### The Story
This telecom dataset tells a clear story: **customers leave when they feel trapped on expensive plans without seeing the value.**

Month-to-month contract holders churn at **3.6×** the rate of two-year customers. Fiber optic subscribers — paying ~$82/month — churn at **41.9%**, the highest of any segment. Yet customers who've stayed beyond 3 years almost never leave.

### What the Model Found
Our optimised XGBoost model achieves **0.874 ROC-AUC** on held-out data, correctly identifying **78% of churners** before they cancel — giving the retention team a 30-day window to act.

**Top 5 churn drivers (by feature importance):**
1. \`contract_risk\` — month-to-month contract
2. \`tenure\` — early-stage customer (< 12 months)
3. \`charge_per_tenure\` — high cost relative to relationship length
4. \`has_no_support\` — internet service without tech support
5. \`MonthlyCharges\` — absolute monthly spend > $70

### Three Actions to Take Tomorrow
| Action | Target Segment | Expected Uplift |
|---|---|---|
| Offer contract upgrade incentive | Month-to-month, tenure 6–18mo | −18% churn in segment |
| Bundle TechSupport at no cost for 3mo | Fiber optic, no support | −12% churn in segment |
| Proactive outreach call | tenure < 6mo, charges > $65 | −9% churn in segment |

**Estimated overall retention uplift: 12–18% of at-risk segment.**
At an average customer lifetime value of $1,200, retaining 200 additional customers = **$240K annual revenue protection.**`,
  },
]

export const MOCK_INIT_LINES = [
  '📂 Scanning dataset: demo_telecom_churn.csv',
  '   Files : 1  |  Types : csv',
  '🚀 Starting phase-based pipeline | run_id: test-demo',
  '   Goal  : Predict customer churn. Optimise for ROC-AUC.',
  '',
  '── Phase 1 · Data Understanding ──────────────────────',
]
