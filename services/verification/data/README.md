# Mock Data for JuraGPT Auditor

This directory contains comprehensive mock data for testing the verification system.

## 📂 File Structure

### Core Data Files

- **`laws.json`** - 30+ German laws from BGB, StGB, ZPO, GG, HGB
- **`cases.json`** - 20+ court decisions from BGH, BVerfG, LAG, etc.
- **`mock_queries.json`** - 25+ legal questions covering various areas
- **`mock_answers.json`** - 50+ LLM-generated answers with varying quality levels
- **`edge_cases.json`** - 15+ challenging verification scenarios

### Generated Variants

- **`variants/answer_variants.json`** - Programmatically generated answer variations
- **`variants/query_variants.json`** - Query rephrasing variants
- **`variants/generation_stats.json`** - Generation statistics

## 📊 Data Categories

### Laws Coverage

- **Civil Law (BGB)**: Tort law (§823), Contract law (§433, §535, §611, §631), AGB (§305, §307), Inheritance (§1922, §1924)
- **Criminal Law (StGB)**: Bodily harm (§223), Theft (§242), Fraud (§263)
- **Constitutional Law (GG)**: Fundamental rights (Art. 1-5, 12, 14)
- **Procedural Law (ZPO)**: Civil procedure (§253, §286, §91)
- **Commercial Law (HGB)**: Merchant law (§1), Partnerships (§105, §161), Accounting (§238)

### Answer Quality Distribution

- **High Confidence (✅ Verified)**: ~40% - Fully supported by sources
- **Medium Confidence (⚠️ Review)**: ~35% - Partially supported or heavily paraphrased
- **Low Confidence (🚫 Rejected)**: ~25% - Hallucinations or unsupported claims

## 🧪 Test Scenarios

### `mock_answers.json` Examples

1. **Fully Verified** (`a001`, `a003`, `a004`, etc.)
   - Answer directly quotes or closely paraphrases sources
   - High semantic similarity (>0.85)
   - Expected: `confidence >= 0.80`, `label = "✅ Verified"`

2. **Partially Supported** (`a002`, `a010`, `a017`, etc.)
   - Answer contains some correct information but adds unsupported claims
   - Medium similarity (0.65-0.80)
   - Expected: `confidence 0.60-0.80`, `label = "⚠️ Review"`

3. **Hallucinated** (`a027_hallucination`, `a028_hallucination`, etc.)
   - Answer contradicts sources or invents information
   - Low similarity (<0.60)
   - Expected: `confidence < 0.60`, `label = "🚫 Rejected"`

### `edge_cases.json` Challenges

- **Contradictory sources** - When retrieved snippets conflict
- **Outdated information** - Facts not in legal database
- **Heavy paraphrasing** - Correct but differently worded
- **Multiple legal bases** - Synthesizing from multiple sources
- **Subtle errors** - Small numeric or procedural mistakes
- **Technical terminology** - Legal jargon not explicitly defined
- **Negative statements** - "No, X is not required"
- **Conditional logic** - If-then reasoning
- **Comparative statements** - Differences between concepts

## 🛠️ Generating Additional Data

Run the variant generator to create more test data:

```bash
python scripts/generate_variants.py
```

This creates:
- Synonym replacements (e.g., "vorsätzlich" → "absichtlich")
- Paraphrased versions (sentence reordering)
- Controlled hallucinations (false absolutes, incorrect numbers)

## 📈 Data Statistics

| Category | Count | Description |
|----------|-------|-------------|
| Laws | 30 | German statutes across 5 legal areas |
| Cases | 22 | Court decisions from 7 different courts |
| Queries | 25 | Legal questions (basic to advanced) |
| Base Answers | 50 | LLM responses with varying quality |
| Edge Cases | 15 | Challenging verification scenarios |
| **Total Examples** | **142** | Comprehensive test coverage |

## 🎯 Usage in Tests

### Unit Tests
```python
from pathlib import Path
import json

# Load test data
data_dir = Path("data")
answers = json.load(open(data_dir / "mock_answers.json"))

# Test specific scenario
verified_answer = next(a for a in answers if a["id"] == "a001")
assert verify_answer(verified_answer) >= 0.80
```

### Integration Tests
```python
# Test full pipeline with edge cases
edge_cases = json.load(open(data_dir / "edge_cases.json"))

for case in edge_cases:
    result = verification_service.verify(
        answer=case["generated_answer"],
        sources=case["retrieved_snippets"]
    )
    assert result["behavior"] == case["expected_behavior"]
```

## 📝 Data Format Specifications

### Answer Object
```json
{
  "id": "a001",
  "query_id": "q001",
  "generated_answer": "Nach §823 Abs. 1 BGB haftet...",
  "expected_confidence": "high",
  "expected_label": "verified",
  "retrieved_snippets": [
    {
      "source_id": "bgb_823_1",
      "text": "Wer vorsätzlich oder fahrlässig...",
      "score": 0.98
    }
  ]
}
```

### Edge Case Object
```json
{
  "id": "edge_001_contradiction",
  "scenario": "contradictory_sources",
  "query": "...",
  "generated_answer": "...",
  "retrieved_snippets": [...],
  "expected_behavior": "Should verify main statement...",
  "challenge": "Answer correct but partially inferred"
}
```

## 🔄 Updating Data

To add new examples:
1. Edit relevant JSON file manually
2. Run `scripts/generate_variants.py` to create variations
3. Run tests to validate: `pytest tests/`

## 📖 References

- **BGB**: https://www.gesetze-im-internet.de/bgb/
- **StGB**: https://www.gesetze-im-internet.de/stgb/
- **GG**: https://www.gesetze-im-internet.de/gg/
- **Court Decisions**: https://openjur.de/

---

**Last Updated**: Generated for JuraGPT Auditor v0.1.0
