import pytest
import pandas as pd
import sys
import os
from datetime import datetime

# Menambahkan root project ke sys.path untuk bisa melakukan import modul 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.etl_batch import transform_data

def test_transform_data_empty():
    """Menguji fungsi transform_data dengan DataFrame kosong."""
    empty_df = pd.DataFrame()
    result = transform_data(empty_df)
    assert result.empty

def test_transform_data_cleansing_and_aggregation():
    """Menguji proses cleansing (deduplikasi, validasi numerik) dan agregasi metrics."""
    raw_data = [
        {
            "transaction_id": "tx-1",
            "user_id": "u-1",
            "amount": 1000,
            "merchant_category": "Food",
            "location": "Jakarta",
            "timestamp": "2026-07-09T10:00:15Z"
        },
        {
            "transaction_id": "tx-1", # Duplikat ID transaksi (harus diabaikan)
            "user_id": "u-1",
            "amount": 1000,
            "merchant_category": "Food",
            "location": "Jakarta",
            "timestamp": "2026-07-09T10:00:15Z"
        },
        {
            "transaction_id": "tx-2",
            "user_id": "u-2",
            "amount": "2000", # Jumlah berbentuk string (harus dikonversi)
            "merchant_category": "Food",
            "location": "Bandung",
            "timestamp": "2026-07-09T10:00:45Z"
        },
        {
            "transaction_id": "tx-3",
            "user_id": "u-3",
            "amount": "invalid", # Nominal yang tidak valid (harus menjadi 0)
            "merchant_category": "Electronics",
            "location": "Surabaya",
            "timestamp": "2026-07-09T10:01:10Z"
        }
    ]
    
    df_raw = pd.DataFrame(raw_data)
    df_agg = transform_data(df_raw)
    
    # 1. Pastikan DataFrame hasil tidak kosong
    assert not df_agg.empty
    
    # 2. Verifikasi Data Cleansing dan Agregasi untuk Kategori 'Food' di menit '10:00'
    # tx-1 dan tx-2 adalah kategori food. tx-1 yang ganda akan tersisa 1 record.
    # Total nominal = 1000 (tx-1) + 2000 (tx-2) = 3000
    # Volume = 2 transaksi unik
    
    # Konversi string pencarian datetime ke format datetime numpy agar match dengan kolom Pandas
    target_time_1 = pd.to_datetime('2026-07-09T10:00:00Z')
    food_10_00 = df_agg[(df_agg['merchant_category'] == 'Food') & (df_agg['metric_time'] == target_time_1)]
    
    assert len(food_10_00) == 1, "Hanya boleh ada 1 baris agregasi untuk rentang 1 menit dan 1 kategori"
    assert food_10_00.iloc[0]['total_amount'] == 3000
    assert food_10_00.iloc[0]['transaction_volume'] == 2
    
    # 3. Verifikasi Error Handling Nominal untuk Kategori 'Electronics' di menit '10:01'
    # tx-3 memiliki amount "invalid", harus ter-cast jadi 0 karena rules pd.to_numeric(errors='coerce')
    target_time_2 = pd.to_datetime('2026-07-09T10:01:00Z')
    electronics_10_01 = df_agg[(df_agg['merchant_category'] == 'Electronics') & (df_agg['metric_time'] == target_time_2)]
                               
    assert len(electronics_10_01) == 1
    assert electronics_10_01.iloc[0]['total_amount'] == 0, "Nominal invalid harus diset menjadi 0"
    assert electronics_10_01.iloc[0]['transaction_volume'] == 1
