#!/bin/bash

# Pastikan script akan berhenti jika ada error
set -e

# Konfigurasi Environment (Dummy creds untuk LocalStack)
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"

BUCKET_NAME="finpulse-raw-data"
STREAM_NAME="finpulse-transaction-stream"

echo "=========================================================="
echo "Memulai Inisialisasi Resource AWS di LocalStack (awslocal)"
echo "=========================================================="

# 1. Membuat S3 Bucket
echo "[1/3] Membuat S3 Bucket: $BUCKET_NAME..."
awslocal s3 mb s3://$BUCKET_NAME
echo "S3 Bucket berhasil dibuat!"

# 2. Membuat Kinesis Data Stream (1 shard cukup untuk percobaan lokal)
echo "[2/3] Membuat Kinesis Data Stream: $STREAM_NAME..."
awslocal kinesis create-stream \
    --stream-name $STREAM_NAME \
    --shard-count 1 \
    --region $AWS_DEFAULT_REGION

# Menunggu Kinesis Stream hingga statusnya "ACTIVE"
echo "Menunggu Stream siap (ACTIVE)..."
awslocal kinesis wait stream-exists --stream-name $STREAM_NAME
echo "Kinesis Stream berhasil dibuat dan aktif!"

# 3. Membuat DynamoDB Table untuk Fraud Detection
echo "[3/4] Membuat DynamoDB Table: HighRiskTransactions..."
awslocal dynamodb create-table \
    --table-name HighRiskTransactions \
    --attribute-definitions AttributeName=transaction_id,AttributeType=S \
    --key-schema AttributeName=transaction_id,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region $AWS_DEFAULT_REGION

echo "DynamoDB Table berhasil dibuat!"

# 4. Verifikasi Pengecekan
echo "[4/4] Verifikasi Resources yang Terbuat:"
echo "- List S3 Buckets:"
awslocal s3 ls

echo "- List Kinesis Streams:"
awslocal kinesis list-streams

echo "- List DynamoDB Tables:"
awslocal dynamodb list-tables

echo "=========================================================="
echo "Setup Selesai! Environment LocalStack siap digunakan."
echo "=========================================================="
