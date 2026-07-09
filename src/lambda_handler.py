import json
import os
import boto3
import uuid
from datetime import datetime

# Deteksi apakah berjalan di dalam environment LocalStack
# LocalStack secara otomatis meng-inject LOCALSTACK_HOSTNAME pada container Lambda
localstack_hostname = os.environ.get('LOCALSTACK_HOSTNAME')

if localstack_hostname:
    endpoint_url = f"http://{localstack_hostname}:4566"
else:
    # Fallback saat testing secara lokal di host machine
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')

# Inisialisasi AWS Clients (S3 dan Kinesis) menuju LocalStack
s3_client = boto3.client('s3', endpoint_url=endpoint_url, region_name='us-east-1')
kinesis_client = boto3.client('kinesis', endpoint_url=endpoint_url, region_name='us-east-1')

S3_BUCKET = os.environ.get('S3_BUCKET', 'finpulse-raw-data')
KINESIS_STREAM = os.environ.get('KINESIS_STREAM', 'finpulse-transaction-stream')

def lambda_handler(event, context):
    """
    Fungsi utama AWS Lambda untuk Ingestion Data.
    Menerima payload dari API Gateway, lalu:
    1. Menyimpan ke S3 (dengan partisi waktu).
    2. Mengirim data mentah (streaming) ke Kinesis.
    """
    try:
        # Ekstrak body dari API Gateway event (biasanya di-stringify)
        if 'body' in event:
            payload = json.loads(event['body'])
        else:
            payload = event  # Fallback jika fungsi di-invoke secara langsung tanpa API Gateway

        # Gunakan timestamp dari payload atau generate waktu saat ini
        tx_timestamp = payload.get('timestamp', datetime.utcnow().isoformat())
        # Ubah format string ISO menjadi objek datetime
        dt_obj = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
        
        # ---------------------------------------------------------
        # 1. Kirim data ke Amazon Kinesis Data Stream
        # ---------------------------------------------------------
        # Gunakan user_id sebagai partition key untuk mendistribusikan data ke shards
        partition_key = payload.get('user_id', str(uuid.uuid4()))
        
        kinesis_client.put_record(
            StreamName=KINESIS_STREAM,
            Data=json.dumps(payload),
            PartitionKey=partition_key
        )
        
        # ---------------------------------------------------------
        # 2. Simpan data mentah ke Amazon S3 (Data Lake)
        # ---------------------------------------------------------
        year = dt_obj.strftime('%Y')
        month = dt_obj.strftime('%m')
        day = dt_obj.strftime('%d')
        tx_id = payload.get('transaction_id', str(uuid.uuid4()))
        
        # Format S3 Key (Partisi berdasarkan tanggal)
        s3_key = f"year={year}/month={month}/day={day}/{tx_id}.json"
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(payload),
            ContentType='application/json'
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Transaksi sukses diproses ke S3 & Kinesis', 'transaction_id': tx_id})
        }

    except Exception as e:
        print(f"Error dalam pemrosesan transaksi: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
