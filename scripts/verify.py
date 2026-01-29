"""
Excel Verification Script

Verifies data integrity of the Excel export file.
Run from project root: python scripts/verify.py

Author: Your Name
Version: 2.0.0
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

EXCEL_FILE = os.path.join('data', 'orders.xlsx')


def verify_excel():
    """Verify Excel file integrity after simulation."""
    
    print("=" * 60)
    print("🔍 EXCEL VERIFICATION REPORT")
    print("=" * 60)
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📄 File: {EXCEL_FILE}")
    print("=" * 60)
    
    # Check if file exists
    if not os.path.exists(EXCEL_FILE):
        print("\n❌ Excel file not found!")
        print("   Run the simulation first: python scripts/simulate.py")
        return False
    
    # Load Excel file
    try:
        df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
        print(f"\n✅ File loaded successfully!")
    except Exception as e:
        print(f"\n❌ Could not read Excel file: {e}")
        return False
    
    # Statistics
    print(f"\n📊 STATISTICS:")
    print(f"   Total Orders: {len(df)}")
    print(f"   Columns: {len(df.columns)}")
    
    # Check required columns
    required = ['order_id', 'customer_name', 'total_amount', 'order_status']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        print(f"\n⚠️ Missing Columns: {missing}")
    else:
        print(f"\n✅ All required columns present")
    
    # Check duplicates
    if 'order_id' in df.columns:
        duplicates = df['order_id'].duplicated().sum()
        if duplicates > 0:
            print(f"\n⚠️ {duplicates} duplicate order IDs found!")
        else:
            print(f"✅ No duplicate order IDs")
    
    # Revenue
    if 'total_amount' in df.columns:
        total = df['total_amount'].sum()
        avg = df['total_amount'].mean()
        print(f"\n💰 REVENUE:")
        print(f"   Total: ${total:.2f}")
        print(f"   Average: ${avg:.2f}")
    
    # Sample data
    print(f"\n📋 RECENT ORDERS:")
    print("-" * 60)
    if len(df) > 0:
        cols = ['order_id', 'customer_name', 'total_amount', 'order_status']
        cols = [c for c in cols if c in df.columns]
        print(df[cols].tail(5).to_string(index=False))
    
    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    verify_excel()