# Biomarker Concordance Pipeline

A production-grade Nextflow DSL2 germline variant calling pipeline with integrated biomarker reproducibility analysis. Implements the same algorithmic stages as the Illumina DRAGEN workflow using open-source equivalents, benchmarks concordance against the GIAB HG001 v4.2.1 truth set, and quantifies inter-run VAF reproducibility using clinical-grade statistical methods.

[![CI](https://github.com/gbadedata/biomarker-concordance-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/gbadedata/biomarker-concordance-pipeline/actions/workflows/ci.yml)
![Nextflow](https://img.shields.io/badge/nextflow-%E2%89%A523.10.0-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [DRAGEN equivalence](#dragen-equivalence)
- [Pipeline stages](#pipeline-stages)
- [Reproducibility analysis](#reproducibility-analysis)
- [Quality monitoring](#quality-monitoring)
- [Quick start](#quick-start)
- [Running on AWS Batch](#running-on-aws-batch)
- [API reference](#api-reference)
- [Dashboard](#dashboard)
- [Infrastructure](#infrastructure)
- [Development](#development)
- [Design decisions](#design-decisions)
- [Known limitations](#known-limitations)

---

## Overview

Sequencing labs that run the same sample repeatedly — across instruments, reagent lots, or days — need two things answered with statistical rigour:

1. **Accuracy** — do my variant calls agree with a validated truth set?
2. **Reproducibility** — are my quantitative biomarker measurements stable across runs?

Without a structured pipeline and quality monitoring framework, those answers live in spreadsheets. This project replaces the spreadsheet.

### What it produces

| Output | Description |
|---|---|
| Per-sample VCF | BQSR-recalibrated, VEP-annotated |
| hap.py concordance report | Precision, recall, F1, Cohen's κ vs GIAB HG001 v4.2.1 |
| Reproducibility report | ICC(A,1), Bland-Altman, CV across replicate runs |
| Levey-Jennings data | Westgard rule violations on VAF series |
| Concordance trend | Mann-Kendall test on run-over-run F1/precision/recall |
| MultiQC report | Aggregated FastQC, GATK, samtools metrics |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Input: samplesheet.csv + paired FASTQs (local or S3)       │
└──────────────────────────┬──────────────────────────────────┘
                           │ Nextflow DSL2
          ┌────────────────▼────────────────┐
          │      FastQC + TrimGalore         │  QC · adapter trimming
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │   BWA-MEM2 align → samtools sort │  Alignment to GRCh38
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │      GATK MarkDuplicates         │  Deduplication
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │  GATK BaseRecalibrator + ApplyBQSR│  BQSR
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │  GATK HaplotypeCaller (GVCF)     │  Germline variant calling
          │       → GenotypeGVCFs            │
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │       Ensembl VEP 110            │  Clinical annotation
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │  hap.py vs GIAB HG001 v4.2.1    │  GA4GH concordance benchmark
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │    Reproducibility engine        │  ICC · Bland-Altman · CV
          │      Quality monitor             │  Westgard · Mann-Kendall
          └────────────────┬────────────────┘
          ┌────────────────▼────────────────┐
          │  FastAPI + PostgreSQL + S3       │  REST API
          │      Streamlit dashboard         │  Quality monitoring UI
          └─────────────────────────────────┘
```

---

## DRAGEN equivalence

This pipeline does not replicate DRAGEN's FPGA acceleration or proprietary scoring. It implements the same processing **stages** using open-source tools that apply equivalent algorithms:

| DRAGEN stage | This pipeline | Notes |
|---|---|---|
| Adapter trimming | TrimGalore 0.6.10 | Cutadapt-based |
| Alignment to GRCh38 | BWA-MEM2 2.2.1 | Same algorithm; FPGA is the only practical difference |
| Duplicate marking | GATK MarkDuplicates 4.5.0.0 | Optical duplicate distance 2500 |
| BQSR | GATK BaseRecalibrator + ApplyBQSR | Identical step |
| Germline variant calling | GATK HaplotypeCaller (GVCF mode) | Local de-novo assembly, Smith-Waterman |
| Annotation | Ensembl VEP 110 + ClinVar | Clinical impact, population frequencies |
| Concordance benchmarking | hap.py 0.3.15 | GA4GH benchmark standard |

The concordance analysis quantifies how closely the open-source outputs agree with the GIAB truth set — the same benchmarking a lab runs when evaluating whether DRAGEN is worth the licence cost.

---

## Pipeline stages

### Samplesheet

```csv
sample,fastq_1,fastq_2,sex,replicate
HG001_rep1,s3://bucket/HG001_R1.fastq.gz,s3://bucket/HG001_R2.fastq.gz,F,1
HG001_rep2,s3://bucket/HG001_R1.fastq.gz,s3://bucket/HG001_R2.fastq.gz,F,2
HG001_rep3,s3://bucket/HG001_R1.fastq.gz,s3://bucket/HG001_R2.fastq.gz,F,3
```

The same `sample` across multiple `replicate` rows enables reproducibility analysis. Duplicate `(sample, replicate)` pairs are rejected at validation time.

### Module containers

| Module | Container | Version |
|---|---|---|
| FastQC | `biocontainers/fastqc` | 0.12.1 |
| TrimGalore | `quay.io/biocontainers/trim-galore` | 0.6.10 |
| BWA-MEM2 | `quay.io/biocontainers/bwa-mem2` | 2.2.1 |
| GATK | `broadinstitute/gatk` | 4.5.0.0 |
| VEP | `nfcore/vep` | 110.0 |
| hap.py | `hap.py:0.3.15` (built locally) | 0.3.15 |

### hap.py container

hap.py v0.3.15 uses an older manifest format incompatible with Docker Engine ≥ 29. Build locally before running:

```bash
git clone --depth 1 --branch v0.3.15 https://github.com/Illumina/hap.py.git ~/hap.py-src
cd ~/hap.py-src
docker build -f Dockerfile -t hap.py:0.3.15 .
docker run hap.py:0.3.15 hap.py --version
```

---

## Reproducibility analysis

The continuous biomarker is **variant allele frequency (VAF)**, extracted from `FORMAT/AD`:

```
VAF = AD[ALT] / (AD[REF] + AD[ALT])
```

Only biallelic PASS variants with DP ≥ 10 are included. Variants must appear in ≥ 2 replicate runs.

### ICC(A,1)

Two-way mixed effects, absolute agreement, single measures. Absolute agreement detects systematic between-run bias — a 0.10 VAF shift is clinically meaningful regardless of whether it is consistent.

| ICC | Interpretation |
|---|---|
| ≥ 0.90 | Excellent — passes threshold |
| 0.75–0.90 | Good — investigate variance sources |
| 0.50–0.75 | Moderate — likely reagent/instrument variability |
| < 0.50 | Poor — pipeline or sample preparation issue |

### Bland-Altman

Computed for every run pair. Reports mean difference (bias), limits of agreement (mean ± 1.96 SD), proportional bias, and whether bias exceeds 0.05 VAF units.

### CV

Per-variant CV = (SD / mean) × 100. Median CV > 15% triggers an alert.

---

## Quality monitoring

Two frameworks, applied to the correct data types.

### Westgard rules — VAF (continuous measurement)

| Rule | Type | Trigger |
|---|---|---|
| 1₂ₛ | Warning | One value outside ±2SD |
| 1₃ₛ | Rejection | One value outside ±3SD |
| 2₂ₛ | Rejection | Two consecutive values beyond ±2SD same side |
| R₄ₛ | Rejection | Consecutive range exceeds 4SD |
| 4₁ₛ | Rejection | Four consecutive values beyond ±1SD same side |
| 10ₓ | Rejection | Ten consecutive values on same side of mean |

Control limits estimated from first 20 runs (baseline period).

### GA4GH trend monitoring — concordance metrics

- **Threshold monitoring** — runs below configured minimums generate immediate alerts
- **Mann-Kendall trend test** — non-parametric, no normality assumption, appropriate for small samples. A significant declining trend (p < 0.05) alerts even when all values are above threshold

---

## Quick start

### Prerequisites

| Tool | Version |
|---|---|
| Java | ≥ 11 |
| Nextflow | ≥ 23.10.0 |
| Docker | ≥ 20.0 |
| Python | ≥ 3.12 |

### Install

```bash
git clone https://github.com/gbadedata/biomarker-concordance-pipeline.git
cd biomarker-concordance-pipeline

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install pysam cyvcf2 pingouin scipy statsmodels pandas numpy \
  fastapi "sqlalchemy[asyncio]" asyncpg alembic structlog \
  tenacity httpx uvicorn plotly streamlit requests
```

### Test profile (chr20 subset — no data download required)

```bash
nextflow run main.nf -profile test
```

### Stub run (syntax check only, completes in seconds)

```bash
nextflow run main.nf -profile test -stub-run
```

### Full run with your own data

```bash
nextflow run main.nf \
  -profile local \
  --input samplesheet.csv \
  --fasta /ref/Homo_sapiens_assembly38.fasta \
  --fasta_fai /ref/Homo_sapiens_assembly38.fasta.fai \
  --dbsnp /ref/dbsnp_146.hg38.vcf.gz \
  --dbsnp_tbi /ref/dbsnp_146.hg38.vcf.gz.tbi \
  --known_indels /ref/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
  --known_indels_tbi /ref/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz.tbi \
  --giab_truth_vcf /ref/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz \
  --giab_truth_tbi /ref/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi \
  --giab_truth_bed /ref/HG001_GRCh38_1_22_v4.2.1_benchmark.bed \
  --outdir ./results
```

### Reference data

```bash
# GATK resource bundle (GRCh38)
gsutil -m cp gs://genomics-public-data/resources/broad/hg38/v0/Homo_sapiens_assembly38.fasta* .
gsutil -m cp gs://genomics-public-data/resources/broad/hg38/v0/dbsnp_146.hg38.vcf.gz* .
gsutil -m cp gs://genomics-public-data/resources/broad/hg38/v0/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz* .

# GIAB HG001 v4.2.1
wget ftp://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
wget ftp://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi
wget ftp://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.bed
```

---

## Running on AWS Batch

### 1. Provision infrastructure

```bash
cd infrastructure
export TF_VAR_db_password="your-secure-password"

terraform init
terraform plan
terraform apply
```

Note the outputs — you will need `batch_job_queue`, `s3_work_bucket`, `rds_endpoint`.

### 2. Stage reference data to S3

```bash
aws s3 cp Homo_sapiens_assembly38.fasta \
  s3://bcp-pipeline-results-677276115158/reference/
# Repeat for all reference files
```

### 3. Run on Batch

```bash
export AWS_BATCH_QUEUE="bcp-queue"
export S3_WORK_BUCKET="bcp-pipeline-work-677276115158"
export AWS_REGION="eu-west-2"

nextflow run main.nf \
  -profile aws \
  --input s3://bcp-pipeline-input-677276115158/samplesheet.csv \
  --fasta s3://bcp-pipeline-results-677276115158/reference/Homo_sapiens_assembly38.fasta \
  --outdir s3://bcp-pipeline-results-677276115158/runs/run_001/
```

### Estimated AWS cost

| Component | Spec | Approx cost |
|---|---|---|
| Batch compute (Spot) | `m5.4xlarge`, per WGS run | £8–15 |
| RDS PostgreSQL | `db.t3.medium` | £35/month |
| S3 | 1 TB results + reference | £20/month |
| ECR | API image | < £1/month |

Destroy all resources when done:

```bash
terraform destroy
```

---

## API reference

```bash
export DATABASE_URL="postgresql+asyncpg://biomarker:biomarker@localhost:5432/biomarker"
uvicorn api.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health and DB connectivity |
| POST | `/api/v1/runs` | Register a pipeline run |
| GET | `/api/v1/runs` | List runs (filter by sample, status) |
| GET | `/api/v1/runs/{run_id}` | Get a specific run |
| PATCH | `/api/v1/runs/{run_id}` | Update run status |
| POST | `/api/v1/concordance` | Store hap.py metrics |
| GET | `/api/v1/concordance` | List concordance results |
| GET | `/api/v1/concordance/summary/{sample_id}` | Aggregated metrics per sample |
| POST | `/api/v1/reproducibility` | Store reproducibility results |
| GET | `/api/v1/reproducibility` | List results |
| GET | `/api/v1/reproducibility/{sample_id}/latest` | Latest result per sample |
| GET | `/api/v1/alerts` | List active quality alerts |
| PATCH | `/api/v1/alerts/{alert_id}/resolve` | Resolve an alert |

---

## Dashboard

```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`. Requires the API running on port 8000.

Deployable directly on **Domino Data Lab** as a Streamlit app — set `API_BASE_URL` environment variable to point at your deployed API.

---

## Infrastructure

```
infrastructure/
├── main.tf    # Provider, variables
├── vpc.tf     # VPC, subnets, security groups
├── s3.tf      # Four S3 buckets with lifecycle policies and public access blocks
├── rds.tf     # PostgreSQL 16, encrypted, private subnet
├── batch.tf   # Compute environment, job queue, three IAM roles
└── ecr.tf     # Container registry
```

### IAM — least privilege

| Role | Permissions |
|---|---|
| `nextflow-head-role` | Batch submit/describe/cancel · S3 read/write on work + results |
| `batch-job-role` | S3 read on input + reference · S3 write on work + results |
| `api-role` | RDS connect · S3 read on reports |

---

## Development

```bash
# Tests
pytest tests/ -v --tb=short

# Lint
ruff check analysis/ api/ tests/

# API with live reload
uvicorn api.main:app --reload

# Dashboard
streamlit run dashboard/app.py
```

---

## Design decisions

**Why Nextflow DSL2 over Snakemake?** nf-core — the largest collection of peer-reviewed bioinformatics pipelines — is built on Nextflow DSL2. Module conventions (meta map, versions.yml, per-process containers) are directly portable to and from the nf-core ecosystem.

**Why GATK HaplotypeCaller over DeepVariant?** HaplotypeCaller implements the same local de-novo assembly and Smith-Waterman alignment that DRAGEN's germline caller uses. DeepVariant is a neural network approach that is architecturally different from DRAGEN.

**Why ICC(A,1) over ICC(C,1)?** Absolute agreement detects systematic between-run bias. Consistency measures only rank-order correlation and would pass even when one run consistently calls VAF 0.10 higher than another — a clinically meaningful difference.

**Why Mann-Kendall for trend detection?** Non-parametric, no normality assumption, robust to outliers, standard in clinical QC trend analysis. With 10–30 runs (typical monitoring window), parametric tests are unreliable.

**Why PostgreSQL alongside S3?** S3 stores all raw outputs for ad-hoc Athena queries. PostgreSQL serves the API with sub-10ms indexed responses — Athena's 1–3s cold start is unsuitable for synchronous API calls.

**Why Streamlit over Plotly Dash?** Streamlit is directly deployable on Domino Data Lab (named in the role specification) without additional configuration.

---

## Known limitations

| Limitation | Detail |
|---|---|
| hap.py container | Must be built locally — Docker Engine ≥ 29 dropped support for the old manifest format |
| VEP skipped in test profile | VEP cache is 40+ GB; `nfcore/vep` container includes it but test profile sets `--skip_vep true` |
| Full genome AWS Batch | Infrastructure declared and `terraform plan` validated; execution requires staging reference data to S3 |
| Single-sample GVCF | Joint genotyping across a cohort requires GenomicsDB import — not currently implemented |
| Reproducibility requires ≥ 2 replicates | ICC and Bland-Altman are undefined for a single run |

---

## Citation

- **GATK**: Van der Auwera et al., 2013, *Current Protocols in Bioinformatics*
- **BWA-MEM2**: Vasimuddin et al., 2019, *IPDPS*
- **hap.py**: Krusche et al., 2019, *Nature Biotechnology*
- **GIAB**: Zook et al., 2019, *Nature Biotechnology*
- **Nextflow**: Di Tommaso et al., 2017, *Nature Biotechnology*
- **VEP**: McLaren et al., 2016, *Genome Biology*

---

## Licence

MIT
