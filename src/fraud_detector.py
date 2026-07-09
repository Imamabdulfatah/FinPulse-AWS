import json
import os
import boto3
import base64
import requests
from datetime import datetime

# Deteksi apakah berjalan di dalam environment LocalStack
localstack_hostname = os.environ.get('LOCALSTACK_HOSTNAME')
if localstack_hostname:
    endpoint_url = f"http://{localstack_hostname}:4566"
else:
    # Fallback saat testing secara lokal di host machine
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')

# Inisialisasi resource DynamoDB
dynamodb = boto3.resource('dynamodb', endpoint_url=endpoint_url, region_name='us-east-1')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'HighRiskTransactions')
table = dynamodb.Table(DYNAMODB_TABLE)

# Daftar negara yang disimulasikan sebagai "di luar kewajaran" (High Risk)
HIGH_RISK_COUNTRIES = ['North Korea', 'Syria', 'Iran', 'Cuba']

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

def send_slack_alert(transaction):
    """
    Mengirimkan alert ke Slack menggunakan incoming webhook dengan format Block Kit.
    """
    if not SLACK_WEBHOOK_URL:
        print("[WARNING] SLACK_WEBHOOK_URL tidak diset. Alert dilewati.")
        return
        
    amount = transaction.get('amount', 0)
    amount_fmt = f"Rp {amount:,.2f}"
    
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 URGENT: High-Value Fraud Alert 🚨",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Transaction ID:*\n`{transaction.get('transaction_id')}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount:*\n{amount_fmt}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Merchant Category:*\n{transaction.get('merchant_category', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Location:*\n{transaction.get('location', 'Unknown')}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
    }
    
    try:
        res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if res.status_code != 200:
            print(f"[ERROR] Slack alert failed: {res.text}")
        else:
            print("[INFO] Slack alert berhasil dikirim.")
    except Exception as e:
        print(f"[ERROR] Exception Slack alert: {e}")

def is_fraudulent(transaction):
    """
    Fungsi sederhana untuk mendeteksi indikasi fraud.
    Mengembalikan tuple: (boolean_is_fraud, string_reason)
    """
    amount = transaction.get('amount', 0)
    location = transaction.get('location', '')
    
    # Kondisi 1: Nominal tidak wajar (di atas 10.000.000)
    if amount > 10000000:
        return True, f"Nominal transaksi mencurigakan (>{amount})"
    
    # Kondisi 2: Lokasi transaksi berada di negara berisiko tinggi
    for country in HIGH_RISK_COUNTRIES:
        if country.lower() in location.lower():
            return True, f"Lokasi tidak wajar ({location})"
            
    return False, "Aman"

def lambda_handler(event, context):
    """
    Fungsi AWS Lambda untuk membaca Kinesis stream dan memproses fraud detection.
    Event dari Kinesis biasanya berisi batch records (multiple data).
    """
    processed_count = 0
    fraud_count = 0
    
    try:
        for record in event.get('Records', []):
            # Payload di dalam Kinesis event selalu di-encode dengan Base64
            payload_base64 = record['kinesis']['data']
            payload_str = base64.b64decode(payload_base64).decode('utf-8')
            transaction = json.loads(payload_str)
            
            processed_count += 1
            
            # Cek fraud
            is_fraud, reason = is_fraudulent(transaction)
            
            if is_fraud:
                fraud_count += 1
                
                # Format data untuk dimasukkan ke DynamoDB
                item = {
                    'transaction_id': transaction['transaction_id'],
                    'user_id': transaction['user_id'],
                    'amount': transaction['amount'],
                    'merchant_category': transaction.get('merchant_category', 'Unknown'),
                    'location': transaction.get('location', 'Unknown'),
                    'timestamp': transaction['timestamp'],
                    'fraud_reason': reason,
                    'detected_at': datetime.utcnow().isoformat()
                }
                
                # Simpan record fraud ke DynamoDB
                table.put_item(Item=item)
                print(f"[FRAUD ALERT] TX_ID: {transaction['transaction_id']} | Reason: {reason}")
                
                # Integrasi ke Slack jika nominal transaksi melebihi Rp50.000.000
                if transaction.get('amount', 0) > 50000000:
                    send_slack_alert(transaction)
                
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Kinesis stream successfully processed.',
                'processed_records': processed_count,
                'fraud_records_saved': fraud_count
            })
        }
    except Exception as e:
        print(f"Error dalam memproses data Kinesis: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
