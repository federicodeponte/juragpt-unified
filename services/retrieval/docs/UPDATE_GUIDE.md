# JuraGPT Legal Corpus - Update Guide

**Last Updated:** 2025-10-31
**Current Corpus:** 325,456 vectors (274,413 German laws + 51,491 EUR-Lex)

## Overview

This guide explains how to keep your JuraGPT legal corpus up to date with new legislation and court cases.

## Current Status

### Data Sources

| Source | Vectors | Last Updated | Update Frequency |
|--------|---------|--------------|------------------|
| **German Federal Laws** | 274,413 | 2025-10-30 | Daily (source updates) |
| **EUR-Lex (EU Laws)** | 51,491 | Static dataset | Monthly (manual check) |
| **OpenLegalData API** | N/A | Currently DOWN | Daily (when available) |

### Total Collection

- **Total Vectors:** 325,456
- **Collection Status:** green (healthy)
- **Embedding Model:** multilingual-e5-large (1024 dimensions)
- **Vector Database:** Qdrant Cloud (gRPC-enabled)

## Quick Start

### Simple Update (Recommended)

```bash
cd ~/juragpt-rag
./scripts/manual_update.sh
```

This will:
1. Show current corpus statistics
2. Check for new documents
3. Process and upload to Qdrant
4. Display cost estimate

### Preview Changes First

```bash
./scripts/manual_update.sh --dry-run
```

Shows what would be updated without making changes.

### Check Status Only

```bash
./scripts/manual_update.sh --stats
```

Or directly:

```bash
python scripts/update_corpus.py --stats
```

## Update Frequency Recommendations

Based on our analysis:

### **Recommended: Monthly Manual Updates**

**Why:**
- German laws change infrequently (mostly amendments)
- OpenLegalData API is currently down
- EUR-Lex is a comprehensive static dataset
- Avoids ongoing GPU costs
- Your corpus is fresh (just completed)

**When to run:**
- First of each month
- After major legislation changes
- When you notice stale data

**Cost:** $2-10 per update (Modal GPU usage)

### Alternative: Weekly Automated (If Needed Later)

Set up a cron job for automatic updates:

```bash
# Edit crontab
crontab -e

# Add weekly update (Sundays at 2 AM)
0 2 * * 0 /home/federicodeponte/juragpt-rag/scripts/run_update.sh
```

**Cost:** $8-40/month

## Detailed Usage

### Option 1: Wrapper Script (Easiest)

```bash
# Standard update
./scripts/manual_update.sh

# Preview only (no changes)
./scripts/manual_update.sh --dry-run

# Stats only
./scripts/manual_update.sh --stats
```

**Features:**
- ✅ Pre/post update statistics
- ✅ Cost estimates
- ✅ Automatic logging to `logs/manual_updates/`
- ✅ Checks Modal GPU availability
- ✅ Color-coded output

### Option 2: Direct Script (Advanced)

```bash
# Standard incremental update
python scripts/update_corpus.py

# Preview changes
python scripts/update_corpus.py --dry-run

# Force full update (ignore timestamp)
python scripts/update_corpus.py --full

# Limit documents
python scripts/update_corpus.py --max-laws 1000 --max-cases 500

# Show statistics
python scripts/update_corpus.py --stats
```

## Understanding Updates

### Incremental Updates

The update system is smart:

1. **Checks last update timestamp** from `data/update_state.json`
2. **Fetches only NEW documents** since that date
3. **Processes** (normalize → chunk → embed with Modal GPU)
4. **Upserts to Qdrant** (preserves existing vectors)
5. **Saves new timestamp** on success

### Data Sources

**Currently Active:**
- ✅ German Federal Laws (kmein/gesetze GitHub)
- ✅ EUR-Lex static dataset (57K documents)

**Currently Unavailable:**
- ❌ OpenLegalData API (experiencing downtime)
  - Would provide: 57K laws + 251K court cases
  - Check status: https://de.openlegaldata.io/api

### GPU Acceleration

Updates use **Modal GPU** for embeddings:

- **GPU:** NVIDIA A10G
- **Speedup:** 31x faster than CPU
- **Batch Size:** 128 chunks at a time
- **Cost:** ~$0.002 per 1000 vectors

**Example:**
- 5,000 new documents → ~10,000 chunks → ~$0.02 cost

## Monitoring & Verification

### Check Qdrant Collection

```bash
python -c "
from src.storage.qdrant_client import JuraGPTQdrantClient
client = JuraGPTQdrantClient()
info = client.get_collection_info()
print(f'Total vectors: {info[\"points_count\"]:,}')
print(f'Status: {info[\"status\"]}')
"
```

### Review Update Logs

```bash
# Latest update
ls -lt logs/manual_updates/ | head -5

# View specific log
cat logs/manual_updates/update_YYYYMMDD_HHMMSS.log
```

### Update State File

```bash
cat data/update_state.json
```

Shows:
- Last update timestamp
- Documents processed in last update
- Total update runs

## Troubleshooting

### Common Issues

#### 1. OpenLegalData API Down

**Error:** `Connection timeout` or `API unreachable`

**Solution:**
- This is a known issue (API down as of 2025-10-29)
- Update will skip this source
- German laws still update via kmein/gesetze
- No action needed - wait for API recovery

#### 2. Modal GPU Timeout

**Error:** `Modal function timeout`

**Solution:**
```bash
# Reduce batch size
python scripts/update_corpus.py --max-laws 500 --max-cases 500
```

#### 3. Qdrant Connection Failed

**Error:** `Failed to connect to Qdrant`

**Solution:**
- Check internet connection
- Verify `QDRANT_URL` and `QDRANT_API_KEY` in `.env`
- Test connection:
  ```bash
  python -c "from src.storage.qdrant_client import JuraGPTQdrantClient; JuraGPTQdrantClient()"
  ```

#### 4. No New Documents Found

**Message:** `No new documents found - corpus is up to date!`

**This is normal!**

German laws don't update frequently. Try again in a week or month.

### Emergency: Reset Update State

If updates are failing repeatedly:

```bash
# Backup current state
cp data/update_state.json data/update_state.json.backup

# Reset to force full update next time
rm data/update_state.json

# Or manually edit the timestamp
nano data/update_state.json
```

## Cost Management

### Estimated Costs

**Per Update:**
- Small update (1K docs): $0.50 - $2
- Medium update (5K docs): $2 - $5
- Large update (10K+ docs): $5 - $15

**Monthly:**
- Manual monthly: $2 - $10/month
- Weekly automated: $8 - $40/month
- Daily automated: $60 - $200/month

**GPU Usage:**
- Modal A10G: ~$1.10/hour
- Typical update: 5-30 minutes
- Only charged when running

### Reducing Costs

1. **Monthly instead of weekly** updates
2. **Use --dry-run** before actual updates
3. **Limit documents** with `--max-laws` and `--max-cases`
4. **Check for new docs** before running:
   ```bash
   ./scripts/manual_update.sh --dry-run
   ```

## Future Enhancements

### Planned (3-6 months)

- [ ] Git commit tracking for German laws incremental updates
- [ ] EUR-Lex SPARQL API integration
- [ ] Fallback data sources when OpenLegalData is down
- [ ] Email notifications for update failures
- [ ] Automatic weekly/monthly scheduling
- [ ] Health check dashboard

### Long-term (6-12 months)

- [ ] Quarterly full refresh for data quality
- [ ] Document version tracking
- [ ] A/B testing for embedding models
- [ ] Performance metrics tracking

## Best Practices

### Before Running Updates

1. **Check current status:** `./scripts/manual_update.sh --stats`
2. **Preview changes:** `./scripts/manual_update.sh --dry-run`
3. **Ensure Modal GPU deployed:** `modal app list`
4. **Have 10-30 minutes** for the update to complete

### After Running Updates

1. **Verify success:** Check final vector count
2. **Review logs:** Look for errors or warnings
3. **Test retrieval:** Run a sample query to verify quality
4. **Note any issues:** For troubleshooting next time

### Recommended Schedule

```
Week 1: Run update
Week 2-3: Monitor, no action
Week 4: Check dry-run for changes
Month end: Review costs and stats
```

## Advanced Topics

### Manual Qdrant Operations

```python
from src.storage.qdrant_client import JuraGPTQdrantClient

client = JuraGPTQdrantClient()

# Collection info
info = client.get_collection_info()

# Search test
from src.embedding.embedder import LegalTextEmbedder
embedder = LegalTextEmbedder()
query_vec = embedder.encode_text("Was ist das BGB?")
results = client.search(query_vec, top_k=5)
```

### Checkpoint System

Updates use checkpoints (like main ingestion):

```bash
# List checkpoints (if any)
ls -la data/update_checkpoints/

# Resume from checkpoint (automatic)
python scripts/update_corpus.py
```

### Parallel Updates

**DO NOT** run multiple updates simultaneously:
- Lock file prevents this: `data/update.lock`
- Modal GPU costs accumulate
- Qdrant may reject concurrent upserts

## Getting Help

### Logs to Check

1. **Update logs:** `logs/manual_updates/update_*.log`
2. **Modal logs:** `modal app logs juragpt-embedder`
3. **Python errors:** Look for tracebacks in logs

### Reporting Issues

When reporting problems, include:

1. Command run
2. Error message
3. Last 50 lines of log file
4. Output of `--stats` command

### Contact

- **Issues:** https://github.com/your-repo/issues
- **Documentation:** This guide + inline code comments

## Summary

**Current Recommendation:** **Monthly manual updates**

**Quick Command:**
```bash
./scripts/manual_update.sh
```

**Expected Outcome:**
- Duration: 5-30 minutes
- Cost: $2-10 per update
- New vectors: 0-10,000 (depending on new legislation)

Your corpus is currently fresh (325,456 vectors) and comprehensive. Monthly updates are sufficient for most use cases.

---

**Last Verified:** 2025-10-31
**Next Recommended Update:** 2025-12-01
