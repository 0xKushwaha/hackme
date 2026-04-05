# Constraint Discovery System - Complete Guide

## Overview

The **Constraint Discovery System** finds mathematical and compositional relationships in ANY dataset without domain knowledge or hardcoding.

It answers questions like:
- Does `total = component_a + component_b + ...`?
- Does `A = w₁*B + w₂*C + ...`?
- Are features linearly dependent?
- What's the compositional structure of the dataset?

**Works on ANY data**: biomass, sales, sensors, financial, scientific data, etc.

---

## Architecture: 4-Stage Pipeline

### Stage 1: Rank Analysis (Quick)
**Time**: <100ms
**Detects**: If linear dependencies exist
**Output**: Rank deficiency (how many)
**Cost**: ~0 inference

```
Question: "Do features have linear dependencies?"
Method: Compute correlation matrix rank
Output: rank_deficiency = 3 (three linear dependencies detected)
```

**Use case**: Quick screening - if rank_deficiency = 0, skip stages 2-4

---

### Stage 2: Algebraic Detection (Medium)
**Time**: 1-10 seconds (depends on number of features)
**Detects**: Additive relationships (A = B + C) and linear combinations
**Output**: Ranked list of candidates with R²
**Cost**: O(N³) exhaustive search

```
Test all combinations:
- A = B + C? R² = 0.9999 ✓
- A = B - C? R² = 0.0012 ✗
- A = B * C? R² = 0.001 ✗
- D = E + F? R² = 0.9995 ✓
...
Top candidates:
  1. total = gdm + dead (R² = 0.9999)
  2. gdm = green + clover (R² = 0.9998)
  3. ...
```

**Optimization**: For wide datasets (>200 features), test only correlations > 0.8 first

---

### Stage 3: Residual Analysis (Thorough)
**Time**: 5-20 seconds
**Detects**: Non-linear relationships via normalized residuals
**Operations tested**: +, -, *, /, and more
**Output**: Relationships ranked by residual magnitude
**Cost**: Tests multiple operation types

```
For each (target, feature1, feature2) triple:
- target_norm ≈ feature1_norm + feature2_norm? Mean residual = 0.0001 ✓
- target_norm ≈ feature1_norm - feature2_norm? Mean residual = 0.5 ✗
- target_norm ≈ feature1_norm * feature2_norm? Mean residual = 0.3 ✗
...
Finds relationships via normalized residual analysis
```

---

### Stage 4: Statistical Validation (Rigorous)
**Time**: 1-5 seconds per relationship
**Tests**: p-values, confidence intervals, significance
**Output**: Confirmed constraints with statistical confidence
**Cost**: Hypothesis testing

```
For each candidate from Stage 2:
Test: target = sum(components)
Result:
  - R² = 0.9999 (perfect fit)
  - p-value = 2.3e-156 (highly significant)
  - 95% CI: [0.9998, 1.0000]
  - Confidence: HIGH
  - Interpretation: Compositional relationship (legitimate structure)
```

---

## Usage Examples

### Example 1: Programmatic Use

```python
import pandas as pd
from analysis.constraint_detector import ConstraintDiscoveryEngine

# Load data
df = pd.read_csv("biomass_data.csv")

# Run discovery
engine = ConstraintDiscoveryEngine(df)
results = engine.discover_all_constraints(
    enable_stage1=True,
    enable_stage2=True,
    enable_stage3=True,
    enable_stage4=True,
)

# View results
print(f"Rank deficiency: {results['stage1_rank_analysis']['rank_deficiency']}")
print(f"Found {len(results['stage2_algebraic'])} algebraic candidates")
print(f"Validated {len(results['stage4_statistical'])} constraints")

for constraint in results['stage4_statistical']:
    print(f"✓ {constraint['target']} = {constraint['components']}")
    print(f"  R² = {constraint['r_squared']:.4f}, p < 0.001")
```

### Example 2: Via Agent

```python
from agents.constraint_discovery_agent import ConstraintDiscoveryAgent
from agents.agent_config import AgentConfig

# Create agent
config = AgentConfig(activity_level=0.8)
agent = ConstraintDiscoveryAgent(llm=your_llm, config=config)

# Set data access
agent.set_data_access(dataset=df, sampler=sampler, extractor=extractor)

# Discover constraints
analysis = agent.discover_constraints()

# Get results
print(f"Discovered {len(analysis.discovered_constraints)} candidates")
print(f"Validated {len(analysis.validated_constraints)} constraints")
print(analysis.to_text_summary())
```

### Example 3: In Pipeline (Automatic)

```python
from orchestration.orchestrator import Orchestrator

# Setup orchestrator
orch = Orchestrator(agents=agents, llm=llm, memory=memory)

# Run phases (constraint discovery included)
results = orch.run_phases(
    dataset_summary="CSIRO biomass dataset",
    dataset_path="data/train.csv",
    target_col="target",
    phases=[
        DataUnderstandingPhase(orch),  # Includes constraint discovery
        ModelDesignPhase(orch),
    ]
)

# Results include constraint findings
constraint_analysis = results["constraint_discovery"]
```

---

## Constraint Analysis Output

### Data Structure

```python
@dataclass
class Constraint:
    formula: str              # "total = gdm + dead"
    strength: float           # 0.9999 (R² or effect size)
    type: str                 # "additive", "linear_combination"
    components: List[str]     # ["gdm", "dead"]
    target: str               # "total"
    details: Dict             # Full statistical results
    validated: bool           # True if passed Stage 4
    confidence: str           # "low", "medium", "high"

@dataclass
class ConstraintAnalysis(DataObject):
    discovered_constraints: List[Constraint]    # All candidates
    validated_constraints: List[Constraint]     # Validated only
    rank_deficiency: int                        # From rank analysis
    has_compositional_structure: bool
    interpretation: str                         # Human-readable summary
```

### Example Output

```
## Constraint Analysis

Found 3 validated constraints:

1. total = gdm + dead
   Type: additive
   Strength: 0.9999
   Confidence: high
   ✓ Validated

2. gdm = green + clover
   Type: additive
   Strength: 0.9998
   Confidence: high
   ✓ Validated

3. dry_total = dry_gdm + dry_dead
   Type: additive
   Strength: 0.9997
   Confidence: high
   ✓ Validated

Rank deficiency: 3
This indicates compositional features (some are combinations of others)

Interpretation:
Biomass dataset has strong compositional structure -
three target variables are sums of components.
This is legitimate dataset structure (not leakage).
Model should respect these constraints during training.
```

---

## Interpreting Results

### High-Confidence Constraints (R² > 0.99, p < 0.001)

**Interpretation**: Compositional relationship
**Action**:
- Note this is dataset structure, not leakage
- Model can use components to predict total (won't hurt)
- Consider constraint-aware training (enforce total = sum of components)

```python
# Example: In training, enforce constraint
predicted_total = predicted_gdm + predicted_dead
loss = mse(predicted_total, actual_total)
```

### Medium-Confidence Candidates (0.95 < R² < 0.99)

**Interpretation**: Strong but not perfect relationship
**Possible reasons**:
- Measurement error/rounding
- Missing components (partial relationship)
- Data collection anomalies

**Action**: Investigate further manually or via regression diagnostics

```python
# Check residuals
residuals = actual_total - (actual_gdm + actual_dead)
print(f"Mean residual: {residuals.mean()}")
print(f"Max residual: {residuals.max()}")
# If max > 0.1, relationship is imperfect
```

### Low-Confidence Candidates (R² < 0.95)

**Interpretation**: Weak or spurious relationship
**Possible reasons**:
- Coincidental correlation
- Different scales/units
- Non-linear or non-additive relationship

**Action**: Reject or investigate separately

---

## API Reference

### ConstraintDiscoveryEngine

```python
engine = ConstraintDiscoveryEngine(df)

# Full pipeline (all 4 stages)
results = engine.discover_all_constraints(
    enable_stage1=True,
    enable_stage2=True,
    enable_stage3=True,
    enable_stage4=True,
    tolerance=0.99  # R² threshold
)

# Returns dict with:
# {
#   "stage1_rank_analysis": {...},
#   "stage2_algebraic": [...],
#   "stage3_residual": [...],
#   "stage4_statistical": [...],
#   "validated_constraints": [...],
#   "summary": "..."
# }
```

### Individual Detectors

```python
from analysis.constraint_detector import (
    RankAnalysisDetector,
    AlgebraicRelationshipDetector,
    ResidualAnalysisDetector,
    StatisticalRelationshipTester,
)

# Stage 1
rank_info = RankAnalysisDetector.find_dependencies(df, threshold=0.95)
# → {"rank_deficiency": 3, "has_dependencies": True, ...}

# Stage 2
candidates = AlgebraicRelationshipDetector.find_additive_relationships(
    df, tolerance=0.99
)
# → [{"formula": "A = B + C", "r_squared": 0.9999, ...}, ...]

# Stage 3
residuals = ResidualAnalysisDetector.find_all_operations(df, tolerance=0.01)
# → [{"formula": "A = B + C", "mean_residual": 0.0001, ...}, ...]

# Stage 4
test_result = StatisticalRelationshipTester.test_additive_relationship(
    df, target="total", components=["gdm", "dead"]
)
# → {
#    "valid": True,
#    "r_squared": 0.9999,
#    "p_value": 2.3e-156,
#    "statistically_significant": True,
#    "confidence": "high"
#   }
```

### ConstraintDiscoveryAgent

```python
agent = ConstraintDiscoveryAgent(llm=llm)
agent.set_data_access(df, sampler, extractor)

# Discover constraints
analysis = agent.discover_constraints(
    enable_stage1=True,
    enable_stage2=True,
    enable_stage3=True,
    enable_stage4=True,
)

# Get human-readable output via LLM
output = agent.run(context="...", task="Find compositional relationships")
```

### DataRepository

```python
repo = DataRepository(run_id="abc123")

# Store
repo.add_constraint_analysis(analysis)
repo.save()

# Retrieve
latest = repo.get_latest_constraint_analysis()
all_constraints = repo.get_validated_constraints()
print(repo.summary())
```

---

## Performance Characteristics

| Stage | Time | Features Tested | Output |
|-------|------|-----------------|--------|
| 1 | <100ms | N/A (rank only) | Rank deficiency |
| 2 | 1-30s | O(N³) combos | Top K candidates (R² > 0.99) |
| 3 | 5-20s | All pairs + ops | Residual-based relationships |
| 4 | 1-5s | Top K from stage 2 | Validated (p < 0.05) |
| **Total** | **~15-60s** | **Variable** | **Validated constraints** |

### Scaling

- **Small datasets** (N < 50 features): All 4 stages in <10 seconds
- **Medium datasets** (50 < N < 200): Stages 1-3 in 10-30 seconds
- **Large datasets** (N > 200): Use optimized Stage 2 (correlations > 0.8 only)

### Memory

- Each stage: ~100 MB per 10K rows
- Total: <500 MB for typical datasets

---

## Troubleshooting

### "No constraints found"

**Possible reasons**:
1. Dataset has no compositional structure (rank-full)
2. Relationships not strong enough (R² < tolerance)
3. Features have different scales

**Solutions**:
```python
# Lower tolerance threshold
results = engine.discover_all_constraints(tolerance=0.95)

# Check if rank-deficient
rank_info = results["stage1_rank_analysis"]
if rank_info["rank_deficiency"] == 0:
    print("Dataset has full rank - no dependencies expected")

# Scale features
df_scaled = (df - df.mean()) / df.std()
results = engine.discover_all_constraints()  # Retry on scaled data
```

### "Too many false positives"

**Solution**: Raise tolerance threshold or use statistical validation only

```python
# Skip to Stage 4 directly (most rigorous)
results = engine.discover_all_constraints(
    enable_stage1=True,
    enable_stage2=False,  # Skip candidates
    enable_stage3=False,
    enable_stage4=True,   # Validate all promising relationships
)
```

### "Runtime too slow"

**Solution**: Disable expensive stages

```python
# Skip residual analysis (most expensive)
results = engine.discover_all_constraints(
    enable_stage3=False,  # Skip residual analysis
)

# Or: test fewer candidates
results = engine.discover_all_constraints(
    max_tests=1000  # Limit algebraic tests
)
```

---

## Integration with ML Pipeline

### Using Constraints in Training

```python
from sklearn.ensemble import RandomForestRegressor
import numpy as np

# Train separate models for each component
models = {
    "gdm": RandomForestRegressor(...),
    "dead": RandomForestRegressor(...),
}

# Predictions
pred_gdm = models["gdm"].predict(X_test)
pred_dead = models["dead"].predict(X_test)

# Enforce constraint: total = gdm + dead
pred_total = pred_gdm + pred_dead

# This respects the compositional structure
```

### Using Constraints for Validation

```python
# Check if constraint holds in new data
def validate_constraint(actual_total, actual_gdm, actual_dead):
    predicted_sum = actual_gdm + actual_dead
    error = np.abs(actual_total - predicted_sum)
    mean_error = error.mean()

    if mean_error > 0.1:
        print(f"⚠️  Constraint violated (mean error: {mean_error:.4f})")
        return False
    return True
```

---

## Generalization Across Datasets

The system works on **any** dataset because it uses:

1. **Pure mathematics** - No domain assumptions
2. **Statistical tests** - Standard hypothesis testing
3. **Exhaustive search** - Tests all feature combinations
4. **Validation** - Confirms relationships hold

**Examples where it works**:
- Biomass: `total = gdm + dead` ✓
- Sales: `total_sales = online_sales + retail_sales` ✓
- Finance: `total_assets = current_assets + fixed_assets` ✓
- Physics: `energy = kinetic_energy + potential_energy` ✓
- Any dataset with compositional structure

---

## Next Steps

1. **Run on your dataset**:
   ```python
   results = orch.run_phases(
       dataset_path="your_data.csv",
       # Constraint discovery runs automatically
   )
   ```

2. **Review constraints in final report**

3. **Decide on modeling strategy**:
   - Respect constraints (enforce in training)
   - Or use all features (let model learn relationships)

4. **Monitor for constraint violations** in production

---

## References

- Rank analysis: Linear algebra (eigenvalue decomposition)
- Algebraic detection: Least squares regression
- Residual analysis: Normalized differences
- Statistical testing: Scipy stats (linregress, chi2)
