import time
import json
import uuid
import random
import requests
import os
from faker import Faker
from datetime import datetime, timezone

fake = Faker()

# Konfigurasi endpoint API Gateway LocalStack (sesuaikan setelah deploy API Gateway)
API_URL = os.environ.get(
    'API_GATEWAY_URL', 
    'http://localhost:4566/restapis/dummy_api_id/local/_user_request_/transactions'
)

MERCHANT_CATEGORIES = [
    'Groceries', 'Electronics', 'Dining', 'Travel', 
    'Entertainment', 'Utilities', 'Health', 'Retail'
]

def generate_transaction():
    """Menghasilkan payload data transaksi dummy."""
    return {
        "transaction_id": str(uuid.uuid4()),
        "user_id": fake.uuid4(),
        "amount": random.randint(10, 5000),
        "merchant_category": random.choice(MERCHANT_CATEGORIES),
        "location": f"{fake.city()}, {fake.country()}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def main():
    print(f"Memulai simulator transaksi keuangan (high-frequency).")
    print(f"Target API Endpoint: {API_URL}")
    print("-" * 50)
    
    while True:
        tx_data = generate_transaction()
        try:
            # Mengirimkan request POST ke API Gateway
            response = requests.post(API_URL, json=tx_data, timeout=5)
            print(f"[SUCCESS] TX_ID: {tx_data['transaction_id'][:8]}... | Amount: {tx_data['amount']:>4} | Categ: {tx_data['merchant_category'][:10]:>10} | Code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Gagal mengirim data: {e}")
        
        # Simulasi high-frequency (jeda acak 0.05 - 0.2 detik ~ 5-20 tx/detik)
        time.sleep(random.uniform(0.05, 0.2))

if __name__ == "__main__":
    main()
