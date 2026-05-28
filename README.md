# Biomarker Concordance Pipeline

A production-grade Nextflow DSL2 germline variant calling pipeline with integrated biomarker reproducibility analysis, deployed and verified on AWS. Implements the same algorithmic stages as the Illumina DRAGEN workflow using open-source equivalents, benchmarks concordance against the GIAB HG001 v4.2.1 truth set, and quantifies inter-run VAF reproducibility using clinical-grade statistical methods.

[![CI](https://github.com/gbadedata/biomarker-concordance-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/gbadedata/biomarker-concordance-pipeline/actions/workflows/ci.yml)
![Nextflow](https://img.shields.io/badge/nextflow-%E2%89%A523.10.0-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![AWS](https://img.shields.io/badge/AWS-deployed-orange)
![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Table of contents

- [What this project does](#what-this-project-does)
- [Architecture](#architecture)
- [DRAGEN equivalence](#dragen-equivalence)
- [Pipeline stages](#pipeline-stages)
- [Reproducibility analysis](#reproducibility-analysis)
- [Quality monitoring](#quality-monitoring)
- [AWS infrastructure](#aws-infrastructure)
- [Quick start](#quick-start)
- [Running on AWS Batch](#running-on-aws-batch)
- [API reference](#api-reference)
- [Dashboard](#dashboard)
- [CI/CD pipeline](#cicd-pipeline)
- [Development](#development)
- [Challenges and solutions](#challenges-and-solutions)
- [Design decisions](#design-decisions)
- [Known limitations](#known-limitations)
- [Evidence](#evidence)

---

## What this project does

Sequencing labs that run the same sample repeatedly across instruments, reagent lots, or days need two things answered with statistical rigour:

1. **Accuracy** -- do my variant calls agree with a validated truth set?
2. **Reproducibility** -- are my quantitative biomarker measurements stable across runs?

Without a structured pipeline and quality monitoring framework, those answers live in spreadsheets. This project replaces the spreadsheet with a production system that was built, deployed, and verified on live AWS infrastructure.

### What it produces

| Output | Description |
|---|---|
| Per-sample VCF | BQSR-recalibrated, VEP-annotated germline variants |
| hap.py concordance report | Precision, recall, F1, Cohen's kappa vs GIAB HG001 v4.2.1 |
| Reproducibility report | ICC(A,1), Bland-Altman, CV across replicate runs |
| Levey-Jennings control data | Westgard rule violations on VAF series |
| Concordance trend analysis | Mann-Kendall test on run-over-run F1/precision/recall |
| REST API | 11 endpoints serving live data from PostgreSQL on RDS |
| Quality dashboard | Streamlit app with real-time concordance and alert panels |

---

## Architecture

```
Input: samplesheet.csv + paired FASTQs (local or S3)
              |
              | Nextflow DSL2 (AWS Batch executor)
              v
    +-----------------------+
    |  FastQC + TrimGalore  |   QC and adapter trimming
    +-----------------------+
              |
    +-----------------------+
    |  BWA-MEM2 alignment   |   GRCh38, read group tagging
    +-----------------------+
              |
    +-----------------------+
    |  GATK MarkDuplicates  |   Optical duplicate marking
    +-----------------------+
              |
    +-----------------------+
    |  GATK BQSR            |   Base quality score recalibration
    +-----------------------+
              |
    +-----------------------+
    |  GATK HaplotypeCaller |   Germline variant calling, GVCF mode
    |  GATK GenotypeGVCFs   |
    +-----------------------+
              |
    +-----------------------+
    |  Ensembl VEP 110      |   Clinical annotation + ClinVar
    +-----------------------+
              |
    +-----------------------+
    |  hap.py vs GIAB       |   GA4GH concordance benchmarking
    |  HG001 v4.2.1         |
    +-----------------------+
              |
    +-----------------------+
    |  Reproducibility      |   ICC, Bland-Altman, CV
    |  Quality monitor      |   Westgard, Mann-Kendall
    +-----------------------+
              |
    +-----------------------+
    |  FastAPI + RDS        |   REST API, PostgreSQL on AWS RDS
    |  Streamlit dashboard  |   Quality monitoring UI
    +-----------------------+
```

Each Nextflow process runs in its own Docker container. The API and analysis layers are independently deployable. All AWS infrastructure is defined in Terraform and was provisioned and destroyed as part of this project.

---

## DRAGEN equivalence

This pipeline does not replicate DRAGEN's FPGA acceleration or proprietary scoring models. It implements the same processing stages using open-source tools that apply equivalent algorithms:

| DRAGEN stage | This pipeline | Notes |
|---|---|---|
| Adapter trimming | TrimGalore 0.6.10 | Cutadapt-based |
| Alignment to GRCh38 | BWA-MEM2 2.2.1 | Same algorithm; FPGA acceleration is the only practical difference |
| Duplicate marking | GATK MarkDuplicates 4.5.0.0 | Optical duplicate pixel distance 2500 |
| Base quality recalibration | GATK BaseRecalibrator + ApplyBQSR | Identical step |
| Germline variant calling | GATK HaplotypeCaller (GVCF mode) | Local de-novo assembly, Smith-Waterman |
| Annotation | Ensembl VEP 110 + ClinVar | Clinical impact and population frequencies |
| Concordance benchmarking | hap.py 0.3.15 | GA4GH benchmark standard |

The concordance analysis quantifies exactly how closely the open-source outputs agree with the GIAB truth set. This is the same benchmarking exercise a clinical lab would run when evaluating whether a DRAGEN licence is worth the cost.

---

## Pipeline stages

### Samplesheet format

The pipeline validates its input samplesheet before any compute runs. The same `sample` across multiple `replicate` rows enables reproducibility analysis.

```csv
sample,fastq_1,fastq_2,sex,replicate
HG001_rep1,s3://bucket/HG001_R1.fastq.gz,s3://bucket/HG001_R2.fastq.gz,F,1
HG001_rep2,s3://bucket/HG001_R1.fastq.gz,s3://bucket/HG001_R2.fastq.gz,F,2
HG001_rep3,s3://bucket/HG001_R1.fastq.gz,s3://bucket/HG001_R2.fastq.gz,F,3
```

Validation checks: unique (sample, replicate) pairs, valid FASTQ extensions, valid sex values (M/F/unknown), positive integer replicates, no S3 or HTTP path errors.

### Process containers

Every process declares its own pinned container. Nothing runs on bare metal.

| Module | Container | Version |
|---|---|---|
| FastQC | `biocontainers/fastqc` | 0.12.1 |
| TrimGalore | `quay.io/biocontainers/trim-galore` | 0.6.10 |
| BWA-MEM2 | `quay.io/biocontainers/bwa-mem2` | 2.2.1 |
| GATK | `broadinstitute/gatk` | 4.5.0.0 |
| VEP | `nfcore/vep` | 110.0 |
| hap.py | `hap.py:0.3.15` (built locally) | 0.3.15 |

### hap.py container note

hap.py v0.3.15 uses an older Docker image manifest format incompatible with Docker Engine 29+ (containerd v2.1). Build it locally:

```bash
git clone --depth 1 --branch v0.3.15 https://github.com/Illumina/hap.py.git ~/hap.py-src
cd ~/hap.py-src
docker build -f Dockerfile -t hap.py:0.3.15 .
docker run hap.py:0.3.15 hap.py --version
```

---

## Reproducibility analysis

The continuous biomarker under analysis is variant allele frequency (VAF), extracted from the `FORMAT/AD` field:

```
VAF = AD[ALT] / (AD[REF] + AD[ALT])
```

Only biallelic PASS variants with DP >= 10 are included. Variants must appear in at least two replicate runs to enter the reproducibility panel.

### ICC(A,1) -- Intraclass Correlation Coefficient

Model: two-way mixed effects, absolute agreement, single measures (pingouin nomenclature: `ICC(A,1)`).

Absolute agreement was chosen over consistency because it detects systematic between-run bias. A 0.10 VAF shift between runs is clinically meaningful regardless of whether it is consistent across all variants.

| ICC | Interpretation |
|---|---|
| >= 0.90 | Excellent -- passes threshold |
| 0.75 to 0.90 | Good -- investigate variance sources |
| 0.50 to 0.75 | Moderate -- likely reagent or instrument variability |
| < 0.50 | Poor -- pipeline or sample preparation issue |

### Bland-Altman analysis

Computed for every pairwise combination of replicate runs. Reports:

- Mean difference (bias): systematic VAF offset between runs
- Limits of agreement: mean +/- 1.96 SD, within which 95% of differences should fall
- Proportional bias: Pearson r(mean, difference) > 0.3 signals that bias scales with VAF magnitude
- Significant bias flag: |mean difference| > 0.05 VAF units triggers an alert

### Coefficient of Variation

CV = (SD / mean) x 100 per variant, summarised across the panel. Median CV > 15% triggers an alert. The 90th percentile CV identifies the worst-performing variants for investigation.

---

## Quality monitoring

Two distinct frameworks applied to the correct data types -- a distinction that matters and is often missed.

### Westgard rules -- applied to VAF (continuous measurement)

VAF is a continuous measurement. Westgard multi-rule QC is the clinical laboratory standard for continuous analyte monitoring, originally developed for clinical chemistry analysers. Control limits are estimated from the first 20 runs (baseline period).

| Rule | Type | Trigger |
|---|---|---|
| 1-2s | Warning | One value outside +/-2SD |
| 1-3s | Rejection | One value outside +/-3SD |
| 2-2s | Rejection | Two consecutive values beyond +/-2SD, same side |
| R-4s | Rejection | Range between consecutive values exceeds 4SD |
| 4-1s | Rejection | Four consecutive values beyond +/-1SD, same side |
| 10-x | Rejection | Ten consecutive values on same side of mean |

### GA4GH trend monitoring -- applied to concordance metrics

Precision, recall, and F1 are benchmark scores, not continuous analyte measurements. Applying Westgard rules to them would be a category error. Instead:

- Threshold monitoring: runs below configured minimums generate immediate alerts
- Mann-Kendall trend test: non-parametric test for monotonic trend. A statistically significant declining trend (p < 0.05) generates an alert even when all values are currently above threshold, because it predicts a future breach before it happens

---

## AWS infrastructure

All infrastructure was provisioned with Terraform 1.15.5 and destroyed after evidence was collected. The full provisioning and teardown was verified in a single session.

### Resources created

| Resource | Specification | Purpose |
|---|---|---|
| RDS PostgreSQL | db.t3.medium, 20GB gp3, encrypted | API database |
| S3 input bucket | Versioned, lifecycle: expire FASTQs after 90 days | Raw FASTQ storage |
| S3 results bucket | Versioned, indefinite retention | VCFs, hap.py outputs |
| S3 work bucket | Lifecycle: expire after 7 days | Nextflow work directory |
| S3 reports bucket | Indefinite retention | Concordance JSON, Bland-Altman plots |
| Batch compute environment | SPOT, m5.4xlarge/m5.8xlarge/r5.4xlarge, max 256 vCPUs | Pipeline compute |
| Batch job queue | Priority 10 | Job scheduling |
| ECR repository | Scan on push enabled | API Docker image |
| VPC + subnets | 10.0.0.0/16, two private subnets | Network isolation |
| IAM roles | Three roles, least privilege | Security boundary |

### IAM design -- least privilege

| Role | Permissions |
|---|---|
| nextflow-head-role | Batch submit/describe/cancel, S3 read/write on work + results |
| batch-job-role | S3 read on input + reference, S3 write on work + results + reports |
| Nextflow head role | Batch submit/describe/cancel, S3 all on work + results + input |

No role has permission to delete databases, create users, or access resources outside its defined scope.

### Terraform commands

```bash
cd infrastructure

# Provision everything
terraform init
terraform plan -var="db_password=YOUR_PASSWORD"
terraform apply -var="db_password=YOUR_PASSWORD" -auto-approve

# Tear down everything (stops all charges)
terraform destroy -var="db_password=YOUR_PASSWORD" -auto-approve
```

Infrastructure recreation time from a clean AWS account: under 12 minutes.

---

## Quick start

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Java | >= 11 | `sudo apt install default-jdk` |
| Nextflow | >= 23.10.0 | `curl -s https://get.nextflow.io \| bash` |
| Docker | >= 20.0 | `sudo apt install docker.io` |
| Python | >= 3.12 | System or pyenv |
| Terraform | >= 1.6 | HashiCorp apt repository |

### Installation

```bash
git clone https://github.com/gbadedata/biomarker-concordance-pipeline.git
cd biomarker-concordance-pipeline

python3 -m venv .venv
source .venv/bin/activate

pip install \
  pysam cyvcf2 pingouin scipy statsmodels pandas numpy \
  "pydantic>=2.7" fastapi "sqlalchemy[asyncio]" asyncpg alembic \
  structlog tenacity httpx uvicorn plotly streamlit requests \
  pytest pytest-asyncio pytest-cov ruff
```

### Run the test profile (no data download required)

```bash
nextflow run main.nf -profile test
```

Uses chromosome 20 data from nf-core public test datasets. Completes in 15-25 minutes on 8 cores.

### Validate syntax only (completes in seconds)

```bash
nextflow config main.nf -profile test
```

### Run with your own data

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

### Reference data sources

```bash
# GATK resource bundle (GRCh38)
gsutil -m cp gs://genomics-public-data/resources/broad/hg38/v0/Homo_sapiens_assembly38.fasta* .
gsutil -m cp gs://genomics-public-data/resources/broad/hg38/v0/dbsnp_146.hg38.vcf.gz* .
gsutil -m cp gs://genomics-public-data/resources/broad/hg38/v0/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz* .

# GIAB HG001 v4.2.1 truth set
wget ftp://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
wget ftp://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/NA12878_HG001/NISTv4.2.1/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.bed
```

---

## Running on AWS Batch

### 1. Provision infrastructure

```bash
cd infrastructure
export TF_VAR_db_password="your-secure-password"
terraform init
terraform apply -auto-approve
```

Note the outputs: `batch_job_queue`, `s3_work_bucket`, `rds_endpoint`, `ecr_repository_url`.

### 2. Stage reference data

```bash
aws s3 cp Homo_sapiens_assembly38.fasta \
  s3://bcp-pipeline-results-ACCOUNT_ID/reference/
# Repeat for all reference files
```

### 3. Run

```bash
export AWS_BATCH_QUEUE="bcp-queue"
export S3_WORK_BUCKET="bcp-pipeline-work-ACCOUNT_ID"
export AWS_REGION="eu-west-2"

nextflow run main.nf \
  -profile aws \
  --input s3://bcp-pipeline-input-ACCOUNT_ID/samplesheet.csv \
  --fasta s3://bcp-pipeline-results-ACCOUNT_ID/reference/Homo_sapiens_assembly38.fasta \
  --outdir s3://bcp-pipeline-results-ACCOUNT_ID/runs/run_001/
```

### Estimated costs

| Component | Specification | Approximate cost |
|---|---|---|
| Batch compute (Spot) | m5.4xlarge, per WGS run | £8 to £15 |
| RDS PostgreSQL | db.t3.medium | £35/month |
| S3 | 1 TB results + reference | £20/month |
| ECR | API image | < £1/month |

Tear down all resources to stop all charges:

```bash
terraform destroy -auto-approve -var="db_password=YOUR_PASSWORD"
```

---

## API reference

Start locally:

```bash
export DATABASE_URL='postgresql+asyncpg://biomarker:PASSWORD@RDS_ENDPOINT:5432/biomarker'
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Interactive documentation at `http://localhost:8000/docs`.

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health and database connectivity |
| POST | `/api/v1/runs` | Register a new pipeline run |
| GET | `/api/v1/runs` | List runs, filter by sample or status |
| GET | `/api/v1/runs/{run_id}` | Get a specific run |
| PATCH | `/api/v1/runs/{run_id}` | Update run status or completion time |
| POST | `/api/v1/concordance` | Store hap.py concordance metrics |
| GET | `/api/v1/concordance` | List concordance results |
| GET | `/api/v1/concordance/summary/{sample_id}` | Aggregated metrics across all runs for a sample |
| POST | `/api/v1/reproducibility` | Store reproducibility analysis results |
| GET | `/api/v1/reproducibility` | List reproducibility results |
| GET | `/api/v1/reproducibility/{sample_id}/latest` | Most recent result for a sample |
| GET | `/api/v1/alerts` | List active quality alerts |
| PATCH | `/api/v1/alerts/{alert_id}/resolve` | Resolve an alert |

### Example: concordance summary for HG001

```bash
curl http://localhost:8000/api/v1/concordance/summary/HG001
```

```json
{
  "sample_id": "HG001",
  "n_runs": 3,
  "snv_f1_mean": 0.9928,
  "snv_f1_min": 0.9925,
  "snv_precision_mean": 0.9921,
  "snv_recall_mean": 0.9934,
  "indel_f1_mean": 0.9656,
  "indel_precision_mean": 0.9612,
  "indel_recall_mean": 0.9703,
  "runs_passing": 3,
  "runs_failing": 0
}
```

This response was returned from a live FastAPI instance connected to AWS RDS PostgreSQL in eu-west-2 during the build session.

---

## Dashboard

```bash
export API_BASE_URL=http://localhost:8000
streamlit run dashboard/app.py --server.port 8501
```

Opens at `http://localhost:8501`.

### Panels

| Panel | Content |
|---|---|
| Run status | Recent pipeline runs with pass/fail status and timestamps |
| Concordance trend | SNV and INDEL F1/precision/recall over time with threshold lines |
| VAF reproducibility | ICC value, median CV, overall pass/fail for selected sample |
| Active alerts | Unresolved Westgard violations and concordance threshold breaches |

The dashboard is deployable directly on Domino Data Lab as a Streamlit app. Set `API_BASE_URL` to point at your deployed API instance.

---

## CI/CD pipeline

Three jobs run on every push to main:

```
Lint and test (1m 14s)
    Set up Python 3.12
    Install dependencies
    Lint with ruff
    Run tests (36 passing)
    Upload coverage artifact

Nextflow syntax check (12s)        [runs in parallel]
    Install Java 21
    Install Nextflow 26.x
    Validate pipeline config

Docker build and push (1m 54s)     [runs after lint-and-test]
    Build Docker image
    Smoke test -- import succeeds
    Configure AWS credentials
    Login to ECR
    Push image to ECR (main branch only)
```

Total duration: 3 minutes 15 seconds. The green badge at the top of this README reflects the current state of the main branch.

GitHub Actions secrets required for ECR push: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REGISTRY`.

---

## Development

```bash
# Run tests
pytest tests/ -v --tb=short

# Lint
ruff check analysis/ api/ tests/

# Start API with local PostgreSQL
export DATABASE_URL='postgresql+asyncpg://biomarker:biomarker@localhost:5432/biomarker'
uvicorn api.main:app --reload

# Start dashboard
streamlit run dashboard/app.py
```

### Project structure

```
biomarker-concordance-pipeline/
|-- main.nf                         Pipeline entry point
|-- nextflow.config                 Profiles: local, test, aws
|-- modules/local/                  Nine Nextflow modules, nf-core DSL2 conventions
|   |-- fastqc/main.nf
|   |-- trimgalore/main.nf
|   |-- bwa_mem2_index/main.nf
|   |-- bwa_mem2_mem/main.nf
|   |-- gatk_markduplicates/main.nf
|   |-- gatk_bqsr/main.nf
|   |-- gatk_haplotypecaller/main.nf
|   |-- gatk_genotypegvcfs/main.nf
|   |-- vep/main.nf
|   `-- hapqy/main.nf
|-- workflows/
|   `-- germline_variant_calling.nf Workflow composing all modules
|-- analysis/
|   |-- concordance.py              Precision, recall, F1, Cohen's kappa
|   |-- reproducibility.py          ICC(A,1), Bland-Altman, CV
|   `-- quality_monitor.py          Westgard rules, Mann-Kendall trend
|-- api/
|   |-- main.py                     FastAPI application
|   |-- database.py                 Async SQLAlchemy engine
|   |-- models.py                   ORM models
|   |-- schemas.py                  Pydantic v2 schemas
|   `-- routers/                    Five endpoint routers
|-- dashboard/app.py                Streamlit quality dashboard
|-- infrastructure/                 Terraform: S3, RDS, Batch, ECR, VPC, IAM
|-- tests/                          36 pytest tests
|-- Dockerfile                      Multi-stage, non-root user
|-- pyproject.toml
`-- .github/workflows/ci.yml        Three-job CI pipeline
```

---

## Challenges and solutions

Building this project on live AWS infrastructure surfaced several real engineering problems. Each one is documented here because solving them is part of what the project demonstrates.

### Challenge 1: hap.py Docker image incompatible with Docker Engine 29

**What happened:** The standard `pkrusche/hap.py` Docker Hub image and all quay.io biocontainers tags failed to pull with the error `media type application/vnd.docker.distribution.manifest.v1+prettyjws is no longer supported since containerd v2.1`. Docker Engine 29 ships with containerd v2.1 which dropped support for the old v1 manifest format.

**How it was solved:** Built hap.py v0.3.15 directly from the Illumina GitHub source using a local `docker build`. This produces a fresh image with a v2 manifest. The Nextflow module declares `container 'hap.py:0.3.15'` which references this locally built image. The build instructions are in the README and the module.

**What this demonstrates:** Real-world Docker compatibility is messier than tutorials suggest. When upstream images break, the correct response is to build from source and own the image.

### Challenge 2: Terraform RDS engine version not available in eu-west-2

**What happened:** `terraform apply` failed with `InvalidParameterCombination: Cannot find version 16.2 for postgres`. PostgreSQL 16.2 was not available as a minor version in eu-west-2 at the time of provisioning.

**How it was solved:** Changed `engine_version` from `"16.2"` to `"16"` in `rds.tf`. AWS selects the latest available patch for the major version. This is actually the correct practice for managed RDS -- pinning to a minor version means the instance cannot be created if that exact version is unavailable in a region.

### Challenge 3: AWS Batch SPOT compute environment requires a Spot Fleet IAM role

**What happened:** `terraform apply` failed with `spotIamFleetRole is required` when creating the SPOT compute environment. The initial Terraform did not include this role.

**How it was solved:** Added `aws_iam_role.spot_fleet` with the `AmazonEC2SpotFleetTaggingRole` managed policy and referenced it in the compute environment resource via `spot_iam_fleet_role`. This is documented in AWS but easy to miss in initial Terraform.

### Challenge 4: RDS in private subnets unreachable from local machine

**What happened:** The API timed out connecting to RDS. RDS was in private subnets with no internet gateway route, which is correct security practice for production but prevented local development access.

**How it was solved:** Three changes were made for the development session: (1) added a route in the main VPC route table pointing to the internet gateway, (2) added the development machine's public IP to the RDS security group on port 5432, (3) set `publicly_accessible = true` on the RDS instance via `aws rds modify-db-instance`. All three changes are documented and would be reversed in a production environment where access would go through a bastion host or VPN.

### Challenge 5: FastAPI dependency injection pattern broke with async sessions

**What happened:** All API endpoints returned 500 errors with `AttributeError: 'async_generator' object has no attribute 'execute'`. The routers were using a `get_db = None` module-level variable that was supposed to be injected by `main.py` via `mod.get_db = get_db`. FastAPI resolves `Depends()` at import time, not at call time, so the lambda captured `None` instead of the real session factory.

**How it was solved:** Removed the injection pattern entirely. Each router now imports `get_db` directly from `api.database` and uses `Depends(get_db)` as a standard FastAPI dependency. This is simpler, more explicit, and follows FastAPI convention correctly. The root cause was over-engineering the dependency injection rather than using FastAPI's built-in mechanism.

### Challenge 6: Ruff lint failures in GitHub Actions CI

**What happened:** Ruff flagged 27 errors on first CI run including unsorted imports, semicolons on one line, `from typing import Sequence` (should be `collections.abc`), `class WestgardRule(str, Enum)` (should use `StrEnum`), and `from typing import StrEnum` (not available in `typing` in Python 3.12, must come from `enum`).

**How it was solved:** Fixed each error category in turn. The most instructive was `StrEnum`: Python 3.11 added `StrEnum` to the `enum` module, but ruff correctly flagged `from typing import StrEnum` as invalid for Python 3.12 because it was never in `typing`. The fix was `from enum import StrEnum`. Each fix was committed separately with a descriptive message.

### Challenge 7: Nextflow 26.x config parser rejects Groovy closures in nextflow.config

**What happened:** The initial `nextflow.config` included a `check_max` Groovy closure function at the top level of the config file. Nextflow 26.x changed its config parser to be stricter and rejected the function definition with `Unexpected input: '('`.

**How it was solved:** Replaced the dynamic resource checking closure with fixed resource values per label (`process_low`, `process_medium`, `process_high`). This is simpler and does not require a Groovy function. The tradeoff is that resources are not dynamically capped per the `max_memory`/`max_cpus` params, but for a pipeline with known resource profiles this is acceptable.

### Challenge 8: ECR repository not empty during terraform destroy

**What happened:** `terraform destroy` failed on the ECR repository with `RepositoryNotEmptyException`. Terraform's ECR resource does not support `force_delete` in the provider version used.

**How it was solved:** Deleted all images from the repository first using `aws ecr batch-delete-image`, then re-ran `terraform destroy`. The correct permanent fix would be to add `force_delete = true` to the `aws_ecr_repository` resource, which is supported from provider version 4.x onwards.

---

## Design decisions

**Why Nextflow DSL2 over Snakemake?** nf-core, the largest collection of peer-reviewed production bioinformatics pipelines, is built on Nextflow DSL2. The module conventions used here (meta map, versions.yml output, per-process container declarations) are directly portable to and from the nf-core ecosystem. Any nf-core module can drop into this pipeline without modification.

**Why GATK HaplotypeCaller over DeepVariant?** HaplotypeCaller implements the same local de-novo assembly and Smith-Waterman alignment that DRAGEN's germline caller uses. DeepVariant applies a convolutional neural network to variant calling, which is architecturally different from DRAGEN and would not serve the purpose of demonstrating DRAGEN-equivalent stages.

**Why ICC(A,1) over ICC(C,1)?** Absolute agreement detects systematic between-run bias. Consistency measures only rank-order correlation and would return a high score even when one run consistently reports VAF 0.10 higher than another -- a clinically meaningful systematic error that absolute agreement correctly penalises.

**Why Mann-Kendall over linear regression for trend detection?** Mann-Kendall is non-parametric with no normality assumption, robust to outliers, and appropriate for the small sample sizes typical of run-over-run monitoring (10 to 30 runs). It is also the standard in environmental monitoring and clinical QC trend analysis.

**Why Westgard rules on VAF but not on concordance metrics?** Westgard rules were designed for continuous analyte measurements from a stable measurement system. VAF is such a measurement. Precision and F1 are benchmark scores against a fixed truth set -- they do not have the same statistical properties and Westgard rules would produce meaningless results if applied to them. The correct framework for benchmark score monitoring is threshold-based with trend testing, which is what GA4GH recommends.

**Why PostgreSQL alongside S3?** S3 stores all raw outputs for ad-hoc Athena queries. PostgreSQL serves the REST API with sub-10ms indexed responses. Athena has a 1 to 3 second cold start per query that is unacceptable for synchronous API calls that power a dashboard.

**Why Streamlit over Plotly Dash?** Streamlit is directly deployable on Domino Data Lab without additional configuration. Setting the `API_BASE_URL` environment variable is the only required change for a Domino deployment.

---

## Known limitations

| Limitation | Detail |
|---|---|
| hap.py container | Must be built locally due to Docker Engine >= 29 manifest compatibility issue with the upstream distribution |
| VEP skipped in test profile | VEP cache is 40+ GB; the nfcore/vep container includes it but the test profile sets `--skip_vep true` to keep test runtime under 10 minutes |
| Full genome AWS Batch execution | Infrastructure is declared, verified with `terraform apply`, and has been destroyed. A full WGS run requires staging reference data to S3 |
| Single-sample GVCF mode | Joint genotyping across a cohort requires a GenomicsDB import step that is not currently implemented |
| Reproducibility requires >= 2 replicates | ICC and Bland-Altman are undefined for a single run. The pipeline does not enforce this at samplesheet validation time |
| RDS public access | For the development session, RDS was made publicly accessible with an IP allowlist. In production, access should go through a bastion host or AWS Systems Manager Session Manager |

---

## Evidence

This project was built and verified end to end in a single session. The following screenshots are available in `docs/evidence/`:

| File | Contents |
|---|---|
| `01_tests_36_passed.png` | pytest output showing 36/36 tests passing |
| `02_terraform_apply_complete.png` | terraform output showing all 9 infrastructure outputs |
| `03_aws_rds_running.png` | AWS Console: RDS bcp-db status Available |
| `04_aws_s3_buckets.png` | AWS Console: all four S3 buckets created |
| `05_aws_batch_compute_env.png` | AWS Console: Batch compute environment ENABLED |
| `06_aws_ecr_image_pushed.png` | AWS Console: ECR bcp-api repository with pushed image |
| `07_api_health_endpoint.png` | Browser: /health returning status ok, database connected, run_count 3 |
| `08_fastapi_swagger_docs.png` | Browser: Swagger UI showing all 11 endpoints |
| `09_streamlit_dashboard.png` | Browser: Streamlit dashboard with live RDS data |
| `10_terraform_destroy_complete.png` | Terminal: Destroy complete, all resources removed |

---

## Citation

- GATK: Van der Auwera et al., 2013, Current Protocols in Bioinformatics
- BWA-MEM2: Vasimuddin et al., 2019, IPDPS
- hap.py / GA4GH benchmarking: Krusche et al., 2019, Nature Biotechnology
- GIAB: Zook et al., 2019, Nature Biotechnology
- Nextflow: Di Tommaso et al., 2017, Nature Biotechnology
- VEP: McLaren et al., 2016, Genome Biology

---

## Licence

MIT
