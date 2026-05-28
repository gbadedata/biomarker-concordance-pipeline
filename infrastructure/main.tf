terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "biomarker-concordance-pipeline"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region"   { default = "eu-west-2" }
variable "environment"  { default = "dev" }
variable "project_name" { default = "bcp" }
variable "db_password"  { sensitive = true }

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }
