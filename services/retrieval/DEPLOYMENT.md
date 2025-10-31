# JuraGPT RAG - Production Deployment Guide

## Overview

This guide covers deploying the JuraGPT RAG system for production use with:
- Resumable ingestion with checkpointing
- Incremental daily updates
- Automated cron jobs
- Monitoring and notifications

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Initial Ingestion (One-time, ~50-100 hours)            │
│  python scripts/ingest.py --max-laws 150000             │
│                           --max-cases 150000            │
│                                                         │
│  Features:                                              │
│  - Checkpointing (resume after crashes)                │
│  - Data persistence (no re-processing)                  │
│  - Progress tracking                                    │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Daily Incremental Updates (Automated)                  │
│  python scripts/update_corpus.py                        │
│                                                         │
│  Features:                                              │
│  - Fetches only NEW documents                          │
│  - Fast (~5-30 minutes per day)                        │
│  - Upserts to existing collection                      │
│  - No checkpointing needed (quick runs)                │
└─────────────────────────────────────────────────────────┘
```

## ⚠️ Data Source Status (Updated 2025-10-29)

**Primary API (OpenLegalData) is currently down:**
- Connection succeeds but API hangs and times out after 30 seconds
- TLS handshake completes but no response returned
- Status: Waiting for server-side fix

**Alternative Data Sources:**
1. **OpenJur API** (`src/crawlers/openjur.py`) - German court decisions, untested
2. **EUR-Lex** (`src/crawlers/eurlex_dataset.py`) - EU legal documents in English
3. **Wait for OpenLegalData API** - Recommended if timeline allows

**Recommendation:** Start with small test (1k documents) using OpenJur to verify pipeline works, then monitor OpenLegalData API status for full ingestion.

## Step 1: Initial Full Ingestion

### Option A: Start Fresh (⚠️ Requires API to be online)

```bash
# ⚠️ IMPORTANT: Monitor resource usage to prevent VM crashes
# Start resource monitor BEFORE ingestion
nohup ./scripts/monitor_resources.sh $(pgrep -f "python.*ingest.py") \
    > logs/resource_monitor.log 2>&1 &

# Start full ingestion (will take 50-100 hours)
nohup python scripts/ingest.py \
    --max-laws 150000 \
    --max-cases 150000 \
    > logs/initial_ingestion.log 2>&1 &

# Monitor progress
tail -f logs/initial_ingestion.log

# Check checkpoints
python scripts/ingest.py --list-checkpoints
```

### Option A2: Test with Small Batch First (RECOMMENDED)

```bash
# Test with 1,000 documents to verify pipeline works
python scripts/ingest.py --max-laws 500 --max-cases 500

# If successful, gradually increase:
# - 10k documents
# - 50k documents
# - Full 300k documents

# This prevents wasting time if there are issues
```

### Option B: Resume After Crash

```bash
# List available checkpoints
python scripts/ingest.py --list-checkpoints

# Resume from specific checkpoint
python scripts/ingest.py --resume 2025-10-29T10-08-08

# Or manually restart (will resume from last checkpoint)
nohup python scripts/ingest.py \
    --max-laws 150000 \
    --max-cases 150000 \
    --resume <run_id> \
    > logs/resume_ingestion.log 2>&1 &
```

### Checkpoint Management

```bash
# List all checkpoints
python scripts/ingest.py --list-checkpoints

# Example output:
# Run ID                Status    Docs    Chunks   Vectors  Last Updated
# 2025-10-29T10-08-08   running   50000   250000   200000   2025-10-29T22:15:00
#
# To resume: python scripts/ingest.py --resume 2025-10-29T10-08-08

# Delete old checkpoint
python scripts/ingest.py --delete-checkpoint 2025-10-29T10-08-08
```

**Checkpoint Structure:**
```
data/checkpoints/2025-10-29T10-08-08/
├── state.json          # Pipeline state metadata
├── documents.jsonl     # Fetched documents
├── normalized.jsonl    # Normalized documents
└── chunks.jsonl        # Document chunks
```

## Step 2: Set Up Incremental Updates

### Manual Testing

```bash
# Show current stats
python scripts/update_corpus.py --stats

# Example output:
# Last update: 2025-10-29T10:00:00
# Documents in last update: 1523
# Total update runs: 42
# Qdrant collection: juragpt_public_law
# Total vectors: 2456789

# Run update manually
python scripts/update_corpus.py

# Force full update (ignore last timestamp)
python scripts/update_corpus.py --full

# Limit documents per update
python scripts/update_corpus.py --max-laws 1000 --max-cases 1000
```

### Automated Daily Updates (Cron)

```bash
# Test the wrapper script
./scripts/run_update.sh

# Check logs
tail -f logs/update_*.log

# Add to crontab (daily at 2 AM)
crontab -e

# Add this line:
0 2 * * * /home/federicodeponte/juragpt-rag/scripts/run_update.sh
```

### Enable Email Notifications (Optional)

```bash
# Set environment variable
export JURAGPT_ALERT_EMAIL="your-email@example.com"

# Or add to ~/.bashrc for persistence
echo 'export JURAGPT_ALERT_EMAIL="your-email@example.com"' >> ~/.bashrc
source ~/.bashrc

# Test notifications
./scripts/run_update.sh
```

**Email will be sent on:**
- Update failures
- Includes last 50 lines of log
- Contains log file path

## Step 3: Monitoring

### Log Files

```bash
# View logs directory
ls -lh logs/

# Recent updates
tail -n 100 logs/update_$(date +%Y%m%d)_*.log

# Search for errors
grep -i error logs/update_*.log

# Check specific run
cat logs/update_20251029_020000.log
```

### Update Statistics

```bash
# View update history
python scripts/update_corpus.py --stats

# Check Qdrant collection
python -c "
from src.storage.qdrant_client import JuraGPTQdrantClient
client = JuraGPTQdrantClient()
info = client.get_collection_info()
print(f'Collection: {info[\"name\"]}')
print(f'Total vectors: {info[\"points_count\"]}')
print(f'Vectors count: {info[\"vectors_count\"]}')
"
```

### Health Checks

```bash
# Check if update is running
ps aux | grep update_corpus.py

# Check lock file
ls -lh data/update.lock

# Remove stale lock (if process is not running)
rm data/update.lock

# Check disk space
df -h data/
df -h logs/
```

### Resource Monitoring (VM Safety)

```bash
# Monitor a running ingestion process to prevent VM crashes
# This will kill the process if RAM > 85% or free disk < 50GB

# Get PID of ingestion process
INGEST_PID=$(pgrep -f "python.*ingest.py")

# Start resource monitor
./scripts/monitor_resources.sh $INGEST_PID

# Or in background with logging
nohup ./scripts/monitor_resources.sh $INGEST_PID \
    > logs/resource_monitor.log 2>&1 &

# Monitor the monitor
tail -f logs/resource_monitor.log

# Check current resource usage
free -h              # RAM usage
df -h /home          # Disk usage
```

**Resource Monitor Features:**
- Checks every 30 seconds
- Kills process if RAM usage > 85%
- Kills process if free disk < 50GB
- Logs all checks to `logs/resource_monitor.log`
- Automatically exits when monitored process finishes

## Expected Performance

### Initial Ingestion
- **Duration:** 50-100 hours (depends on API speed)
- **Documents:** ~300,000 (150k laws + 150k cases)
- **Chunks:** ~15-20 million
- **Disk usage:** ~5-10 GB (checkpoints + processed data)
- **Memory:** 4-8 GB peak (during embedding)

### Incremental Updates
- **Duration:** 5-30 minutes per day
- **New documents:** ~100-1000 per day
- **Chunks:** ~5000-50000 per day
- **Disk usage:** Minimal (old logs auto-deleted after 30 days)

## Troubleshooting

### Update Fails with "Lock file exists"

```bash
# Check if process is actually running
ps aux | grep update_corpus.py

# If not running, remove stale lock
rm data/update.lock

# Lock automatically removed if >12 hours old
```

### Pipeline Crashes During Ingestion

```bash
# Check available checkpoint
python scripts/ingest.py --list-checkpoints

# Resume from checkpoint
python scripts/ingest.py --resume <run_id>

# Check error in logs
tail -n 500 logs/initial_ingestion.log | grep -i error
```

### Incremental Update Finds No New Documents

This is normal! If no documents were published since last update:
```
✓ No new documents found - corpus is up to date!
```

### API Timeouts

```bash
# Reduce batch size in incremental updates
python scripts/update_corpus.py --max-laws 500 --max-cases 500

# For initial ingestion, checkpointing handles this automatically
# (just resume from checkpoint)
```

### Out of Memory During Embedding

```bash
# Check memory usage
free -h

# If running out of memory during initial ingestion:
# 1. Let it crash (checkpoint will save progress)
# 2. Free up memory
# 3. Resume from checkpoint

python scripts/ingest.py --resume <run_id>
```

### Check Qdrant Connection

```bash
# Test connection
python -c "
from src.storage.qdrant_client import JuraGPTQdrantClient
client = JuraGPTQdrantClient()
print('✓ Connected to Qdrant')
info = client.get_collection_info()
print(f'✓ Collection exists: {info[\"name\"]}')
"
```

## Maintenance

### Cleanup Old Checkpoints

```bash
# List all checkpoints
python scripts/ingest.py --list-checkpoints

# Delete completed/old checkpoints
python scripts/ingest.py --delete-checkpoint <run_id>

# Keep only running checkpoints (in case of crash)
```

### Log Rotation

Automatic log cleanup:
- Wrapper script keeps last 30 days of logs
- Runs automatically on each update
- Manual cleanup: `find logs/ -name "update_*.log" -mtime +30 -delete`

### Backup Qdrant Collection

```bash
# Create snapshot via Qdrant API
curl -X POST "https://YOUR_QDRANT_URL/collections/juragpt_public_law/snapshots"

# Download snapshot
curl "https://YOUR_QDRANT_URL/collections/juragpt_public_law/snapshots/<snapshot-name>" \
    --output backup_$(date +%Y%m%d).snapshot
```

## Production Checklist

Before going to production:

- [ ] Initial ingestion completed successfully
- [ ] Qdrant collection has expected number of vectors
- [ ] Incremental update tested manually
- [ ] Cron job configured and tested
- [ ] Email notifications configured (optional)
- [ ] Log directory has adequate disk space
- [ ] Backup strategy for Qdrant collection
- [ ] Monitoring dashboard setup (optional)
- [ ] Documentation shared with team

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Run `--stats` to verify state
3. Check GitHub issues: https://github.com/your-repo/issues
4. Review TESTING_REPORT.md for known issues

## Next Steps

After deployment:
1. Monitor first few incremental updates
2. Verify data quality in Qdrant
3. Test query/retrieval performance
4. Set up application using the corpus
5. Consider adding monitoring dashboards (Grafana, etc.)
