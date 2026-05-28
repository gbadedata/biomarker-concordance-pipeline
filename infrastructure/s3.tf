resource "aws_s3_bucket" "input" {
  bucket = "${var.project_name}-pipeline-input-${local.account_id}"
}

resource "aws_s3_bucket" "results" {
  bucket = "${var.project_name}-pipeline-results-${local.account_id}"
}

resource "aws_s3_bucket" "work" {
  bucket = "${var.project_name}-pipeline-work-${local.account_id}"
}

resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-pipeline-reports-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "input" {
  bucket = aws_s3_bucket.input.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "results" {
  bucket = aws_s3_bucket.results.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "work" {
  bucket = aws_s3_bucket.work.id
  rule {
    id     = "expire-work"
    status = "Enabled"
    filter {
      prefix = "work/"
    }
    expiration {
      days = 7
    }
  }
}

resource "aws_s3_bucket_public_access_block" "input" {
  bucket                  = aws_s3_bucket.input.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "work" {
  bucket                  = aws_s3_bucket.work.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "s3_input_bucket"   { value = aws_s3_bucket.input.bucket }
output "s3_results_bucket" { value = aws_s3_bucket.results.bucket }
output "s3_work_bucket"    { value = aws_s3_bucket.work.bucket }
output "s3_reports_bucket" { value = aws_s3_bucket.reports.bucket }
