terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------
# AWS Provider Configuration (LocalStack / Offline Mode)
# ---------------------------------------------------------
provider "aws" {
  access_key                  = "test"
  secret_key                  = "test"
  region                      = "us-east-1"

  # Konfigurasi khusus untuk bypass validasi kredensial AWS asli
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  # Arahkan service AWS spesifik ke endpoint LocalStack (localhost:4566)
  endpoints {
    s3       = "http://localhost:4566"
    kinesis  = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
  }
}

# ---------------------------------------------------------
# 1. Amazon S3 Bucket (Raw Data Lake)
# ---------------------------------------------------------
resource "aws_s3_bucket" "raw_data_bucket" {
  bucket = "finpulse-raw-data"
}

# ---------------------------------------------------------
# 2. Amazon Kinesis Data Stream (Speed Layer)
# ---------------------------------------------------------
resource "aws_kinesis_stream" "transaction_stream" {
  name             = "finpulse-transaction-stream"
  shard_count      = 1
  retention_period = 24
}

# ---------------------------------------------------------
# 3. Amazon DynamoDB Table (Fraud Alerts Store)
# ---------------------------------------------------------
resource "aws_dynamodb_table" "high_risk_transactions" {
  name           = "HighRiskTransactions"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S" # Tipe data: String
  }
}
