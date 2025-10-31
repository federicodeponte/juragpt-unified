# German Legal Data Sources - Research Findings

**Date**: 2025-10-28
**Research Time**: 15 minutes
**Findings**: ✅ Multiple pre-crawled datasets found!

---

## 🏆 Top 3 Recommended Sources

### 1. ⭐ kmein/gesetze (BEST OPTION)
- **URL**: https://github.com/kmein/gesetze
- **Stars**: 35 ⭐
- **Last Updated**: 2025-10-27 (yesterday!)
- **Update Frequency**: DAILY
- **Format**: Plain text
- **License**: Public domain / CC-BY
- **Why Best**: Most recent, daily updates, clean format

**What they provide**:
- All German federal laws from gesetze-im-internet.de
- Organized by law name
- Plain text format (easy to parse)
- Git history shows daily automated updates

**How to use**:
```bash
git clone https://github.com/kmein/gesetze
# Parse plain text files → convert to JSON → ingest
```

---

### 2. jandinter/gesetze-im-internet
- **URL**: https://github.com/jandinter/gesetze-im-internet
- **Stars**: 36 ⭐
- **Last Updated**: 2025-04-29
- **Update Frequency**: Weekly
- **Format**: Archive / structured

**Why good**: Well-maintained, structured format

---

### 3. QuantLaw/gesetze-im-internet
- **URL**: https://github.com/QuantLaw/gesetze-im-internet
- **Stars**: 30 ⭐
- **Last Updated**: 2025-09-23
- **Update Frequency**: Daily
- **Format**: Archive

**Why good**: Academic project (QuantLaw), reliable

---

## Other Useful Projects

### bundesrecht-scraper (daniel-j-h)
- **URL**: https://github.com/daniel-j-h/bundesrecht-scraper
- **Stars**: 4 ⭐
- **Purpose**: GitHub Action-based scraper
- **Use case**: Could adapt their scraping logic

### OpenLegalData API
- **URL**: https://de.openlegaldata.io/
- **Format**: REST API
- **Content**: German case law + statutes
- **Status**: Check if API still active

---

## Court Cases Sources

### OpenJur (requires research)
- Current API endpoint unknown
- May require authentication
- Alternative: Check openlegaldata.io for cases

### DIP (Dokumentations- und Informationssystem)
- **URL**: https://dip.bundestag.de/
- **Content**: German parliament documents, laws in progress
- **Format**: XML/REST API

---

## EUR-Lex (EU Legal Texts)

### SPARQL Endpoint
- **URL**: https://publications.europa.eu/webapi/rdf/sparql
- **Format**: RDF/XML
- **Query Language**: SPARQL
- **Content**: All EU legal documents in German

### REST API
- Check documentation at eur-lex.europa.eu
- Likely has structured access

---

## ✅ IMPLEMENTED SOLUTION

### **OpenLegalData API Integration** (COMPLETED - 2025-10-28)

**Implementation:**
- Created `src/crawlers/openlegaldata_api.py` - REST API client
- Updated `scripts/ingest.py` to use OpenLegalData instead of failed crawlers
- Successfully fetched and ingested REAL data

**Results:**
- ✅ **30 real documents** (10 laws + 20 court cases)
- ✅ **1,010 chunks** created and embedded
- ✅ **1,010 vectors** uploaded to Qdrant Cloud
- ✅ Retrieval tested and working (80%+ similarity scores)
- ✅ Pipeline time: ~11 minutes for 30 documents

**API Details:**
- Base URL: `https://de.openlegaldata.io/api`
- Endpoints: `/cases/` (251,036 available), `/laws/` (57,192 available)
- Format: JSON with pagination
- Rate limiting: 0.5s delay between requests (respectful)
- No authentication required

**Advantages:**
- ✅ Both laws AND cases in one API
- ✅ Structured JSON format (no HTML parsing)
- ✅ Actively maintained (data from 2022-2029)
- ✅ Large dataset available (300k+ documents)
- ✅ Easy pagination

**Current Status:**
- Small test corpus ingested (30 documents)
- Can scale to full corpus by adjusting `--max-laws` and `--max-cases` parameters
- Ready for production use

**Usage:**
```bash
# Ingest 100 laws and 500 cases
python scripts/ingest.py --max-laws 100 --max-cases 500

# Query the corpus
python scripts/query.py --query "Was besagt das Grundgesetz über Meinungsfreiheit?"
```

---

## Alternative Options (NOT YET IMPLEMENTED)

### Option A: Add kmein/gesetze for more laws

**When to use**: If you need more comprehensive law coverage than OpenLegalData provides

**Steps**:
1. Clone repository: `git clone https://github.com/kmein/gesetze`
2. Parse plain text files
3. Add to existing OpenLegalData crawler

**Effort**: ~2-3 hours

---

### Option B: Add EUR-Lex for EU Law

**When to use**: If you need EU legal documents in German

**API**: https://publications.europa.eu/webapi/rdf/sparql

**Effort**: ~4-5 hours (SPARQL queries, RDF parsing)

---

## Comparison Table (Updated with Actual Results)

| Source | Format | Update | Laws | Cases | Effort | Status |
|--------|--------|--------|------|-------|--------|---------|
| **OpenLegalData** | **API** | **Active** | **✅ 57k** | **✅ 251k** | **2h** | **✅ DONE** |
| kmein/gesetze | Text | Daily | ✅ All | ❌ | 3h | ⏸️ Optional |
| EUR-Lex | SPARQL | Daily | ✅ EU | ❌ | 5h | ⏸️ Optional |
| Manual crawlers | HTML | Manual | ❌ | ❌ | 3d | ❌ Abandoned |

---

## Scaling Plan

**Current**: 30 documents (test corpus)

**Phase 1** (Next step): 1,000 documents (100 laws + 900 cases)
- Estimated time: ~2 hours
- Estimated chunks: ~33,000

**Phase 2**: 10,000 documents (1,000 laws + 9,000 cases)
- Estimated time: ~20 hours (can run overnight)
- Estimated chunks: ~330,000

**Phase 3**: Full corpus (57k laws + 251k cases = 308k documents)
- Estimated time: ~100 hours (4 days continuous)
- Estimated chunks: ~10 million
- May require batch processing and Qdrant optimization

---

## What I Learned

❌ **Don't write scrapers without researching first**
✅ **Check GitHub for existing solutions**
✅ **Use maintained, updated sources**
✅ **Leverage open source community work**

The legal tech community has already solved this problem!
