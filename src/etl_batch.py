import os
import json
import boto3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone

# ---------------------------------------------------------
# Konfigurasi Environment & Kredensial
# ---------------------------------------------------------
S3_BUCKET = os.environ.get('S3_BUCKET', 'finpulse-raw-data')
AWS_ENDPOINT = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'finpulse_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASS = os.environ.get('DB_PASS', 'postgres')

def get_s3_client():
    return boto3.client('s3', endpoint_url=AWS_ENDPOINT, region_name='us-east-1')

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def extract_data_from_s3(target_date):
    """
    Ekstrak seluruh file JSON dari S3 berdasarkan partisi tanggal (tahun, bulan, hari).
    """
    s3 = get_s3_client()
    year = target_date.strftime('%Y')
    month = target_date.strftime('%m')
    day = target_date.strftime('%d')
    
    prefix = f"year={year}/month={month}/day={day}/"
    print(f"[EXTRACT] Membaca S3 Path: s3://{S3_BUCKET}/{prefix}")
    
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix)
    
    data_list = []
    
    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                response = s3.get_object(Bucket=S3_BUCKET, Key=key)
                content = response['Body'].read().decode('utf-8')
                try:
                    record = json.loads(content)
                    data_list.append(record)
                except json.JSONDecodeError:
                    print(f"[WARNING] Invalid JSON dilewati: {key}")
                    
    df = pd.DataFrame(data_list)
    print(f"[EXTRACT] Total record JSON mentah yang ditemukan: {len(df)}")
    return df

def transform_data(df):
    """
    Cleansing dan Agregasi (Grouping) data menggunakan Pandas.
    """
    if df.empty:
        return df
        
    # 1. Cleansing: Menghapus duplikasi berdasarkan ID Transaksi
    df = df.drop_duplicates(subset=['transaction_id'])
    
    # 2. Cleansing: Pastikan 'amount' adalah numerik
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    
    # 3. Cleansing: Standarisasi format timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    
    # 4. Agregasi: Buat dimensi waktu per menit (Time Series)
    df['metric_time'] = df['timestamp'].dt.floor('min')
    
    # Grouping berdasarkan waktu(menit) dan kategori merchant
    agg_df = df.groupby(['metric_time', 'merchant_category']).agg(
        total_amount=('amount', 'sum'),
        transaction_volume=('transaction_id', 'count')
    ).reset_index()
    
    print(f"[TRANSFORM] Total record setelah diagregasi: {len(agg_df)}")
    return agg_df

def load_data_to_postgres(df):
    """
    Menulis DataFrame hasil agregasi ke PostgreSQL menggunakan eksekusi batch yang efisien (execute_values).
    Menerapkan UPSERT (INSERT ON CONFLICT DO UPDATE) agar idempotent (bisa di-run berulang kali dengan aman).
    """
    if df.empty:
        print("[LOAD] Tidak ada data yang dimuat ke PostgreSQL.")
        return
        
    insert_query = """
        INSERT INTO merchant_metrics_per_minute (
            metric_time, merchant_category, total_amount, transaction_volume, last_updated_at
        ) VALUES %s
        ON CONFLICT (metric_time, merchant_category)
        DO UPDATE SET
            total_amount = EXCLUDED.total_amount,
            transaction_volume = EXCLUDED.transaction_volume,
            last_updated_at = EXCLUDED.last_updated_at;
    """
    
    now = datetime.now(timezone.utc)
    # Ubah baris dataframe ke tuple untuk execute_values psycopg2
    records = []
    for _, row in df.iterrows():
        records.append((
            row['metric_time'],
            row['merchant_category'],
            row['total_amount'],
            row['transaction_volume'],
            now
        ))
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            execute_values(cur, insert_query, records)
        conn.commit()
        print(f"[LOAD] Berhasil memasukkan {len(records)} record ke dalam PostgreSQL finpulse_db.")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Gagal menyimpan ke database: {e}")
    finally:
        conn.close()

def main():
    print("=" * 50)
    print("Memulai proses Batch Layer (ETL)")
    print("=" * 50)
    
    # Mengambil partisi tanggal. Secara default adalah hari ini.
    # Jika menggunakan Airflow (Cron), bisa dimodifikasi menggunakan parameter dari scheduler.
    target_date = datetime.utcnow()
    
    # Jalankan Pipa ETL (Extract, Transform, Load)
    df_raw = extract_data_from_s3(target_date)
    df_agg = transform_data(df_raw)
    load_data_to_postgres(df_agg)
    
    print("=" * 50)
    print("Proses ETL selesai.")

if __name__ == "__main__":
    main()
