# IAM: Batch service role
resource "aws_iam_role" "batch_service" {
  name = "${var.project_name}-batch-service-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "batch.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# IAM: EC2 instance profile
resource "aws_iam_role" "batch_instance" {
  name = "${var.project_name}-batch-instance-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "batch_instance_ecs" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "batch" {
  name = "${var.project_name}-batch-instance-profile"
  role = aws_iam_role.batch_instance.name
}

# IAM: Spot Fleet role — required for SPOT compute environments
resource "aws_iam_role" "spot_fleet" {
  name = "${var.project_name}-spot-fleet-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "spotfleet.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  role       = aws_iam_role.spot_fleet.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

# IAM: Batch job role
resource "aws_iam_role" "batch_job" {
  name = "${var.project_name}-batch-job-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "batch_job_s3" {
  name = "${var.project_name}-batch-job-s3"
  role = aws_iam_role.batch_job.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:HeadObject"]
        Resource = [
          "${aws_s3_bucket.input.arn}/*",
          "${aws_s3_bucket.results.arn}/reference/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.work.arn,
          "${aws_s3_bucket.work.arn}/*",
          aws_s3_bucket.results.arn,
          "${aws_s3_bucket.results.arn}/*",
          aws_s3_bucket.reports.arn,
          "${aws_s3_bucket.reports.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

# IAM: Nextflow head job role
resource "aws_iam_role" "nextflow_head" {
  name = "${var.project_name}-nextflow-head-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "nextflow_head_policy" {
  name = "${var.project_name}-nextflow-head-policy"
  role = aws_iam_role.nextflow_head.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["batch:SubmitJob", "batch:DescribeJobs", "batch:TerminateJob", "batch:CancelJob", "batch:ListJobs"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["s3:*"]
        Resource = [
          aws_s3_bucket.work.arn,
          "${aws_s3_bucket.work.arn}/*",
          aws_s3_bucket.results.arn,
          "${aws_s3_bucket.results.arn}/*",
          aws_s3_bucket.input.arn,
          "${aws_s3_bucket.input.arn}/*"
        ]
      }
    ]
  })
}

# Batch: Compute environment with Spot Fleet role
resource "aws_batch_compute_environment" "main" {
  compute_environment_name = "${var.project_name}-compute-env"
  type                     = "MANAGED"
  state                    = "ENABLED"

  compute_resources {
    type                = "SPOT"
    bid_percentage      = 60
    min_vcpus           = 0
    max_vcpus           = 256
    desired_vcpus       = 0
    instance_type       = ["m5.4xlarge", "m5.8xlarge", "r5.4xlarge"]
    subnets             = aws_subnet.private[*].id
    security_group_ids  = [aws_security_group.batch.id]
    instance_role       = aws_iam_instance_profile.batch.arn
    spot_iam_fleet_role = aws_iam_role.spot_fleet.arn

    tags = { Name = "${var.project_name}-batch-instance" }
  }

  service_role = aws_iam_role.batch_service.arn
  depends_on   = [
    aws_iam_role_policy_attachment.batch_service,
    aws_iam_role_policy_attachment.spot_fleet,
  ]
}

# Batch: Job queue
resource "aws_batch_job_queue" "main" {
  name     = "${var.project_name}-queue"
  state    = "ENABLED"
  priority = 10

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.main.arn
  }
}

output "batch_job_queue"        { value = aws_batch_job_queue.main.name }
output "batch_job_role_arn"     { value = aws_iam_role.batch_job.arn }
output "nextflow_head_role_arn" { value = aws_iam_role.nextflow_head.arn }
