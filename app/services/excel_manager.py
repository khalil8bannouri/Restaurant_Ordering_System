"""
Excel Manager Module
Handles thread-safe Excel file operations using FileLock.
Prevents race conditions when multiple workers try to write simultaneously.
"""

import os
import pandas as pd
from datetime import datetime
from filelock import FileLock, Timeout
from typing import Optional
import json

# Path configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
EXCEL_FILE = os.path.join(DATA_DIR, 'orders.xlsx')
LOCK_FILE = os.path.join(DATA_DIR, 'orders.xlsx.lock')


class ExcelManager:
    """
    Manages Excel file operations with proper locking.
    Ensures data integrity under high concurrency.
    """
    
    # Lock timeout in seconds
    LOCK_TIMEOUT = 30
    
    @classmethod
    def _ensure_data_dir(cls):
        """Create data directory if it doesn't exist"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            print(f"📁 Created data directory: {DATA_DIR}")
    
    @classmethod
    def _get_or_create_dataframe(cls) -> pd.DataFrame:
        """Load existing Excel file or create new DataFrame"""
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
                return df
            except Exception as e:
                print(f"⚠️ Error reading Excel file: {e}")
                # Return empty DataFrame if file is corrupted
                return cls._create_empty_dataframe()
        else:
            return cls._create_empty_dataframe()
    
    @classmethod
    def _create_empty_dataframe(cls) -> pd.DataFrame:
        """Create empty DataFrame with proper columns"""
        columns = [
            'order_id',
            'customer_name',
            'customer_phone',
            'delivery_address',
            'city',
            'zip_code',
            'items',
            'special_instructions',
            'subtotal',
            'tax',
            'delivery_fee',
            'total_amount',
            'payment_intent_id',
            'payment_status',
            'order_status',
            'created_at',
            'exported_at'
        ]
        return pd.DataFrame(columns=columns)
    
    @classmethod
    def export_order(cls, order_data: dict) -> dict:
        """
        Export a single order to Excel file.
        Uses FileLock to prevent concurrent write issues.
        
        Args:
            order_data: Dictionary containing order information
            
        Returns:
            dict: Result with success status and message
        """
        cls._ensure_data_dir()
        
        result = {
            'success': False,
            'message': '',
            'order_id': order_data.get('order_id'),
            'exported_at': None
        }
        
        try:
            # Acquire file lock with timeout
            lock = FileLock(LOCK_FILE, timeout=cls.LOCK_TIMEOUT)
            
            with lock:
                print(f"🔒 Lock acquired for order #{order_data.get('order_id')}")
                
                # Load or create DataFrame
                df = cls._get_or_create_dataframe()
                
                # Prepare new row
                new_row = {
                    'order_id': order_data.get('order_id'),
                    'customer_name': order_data.get('customer_name'),
                    'customer_phone': order_data.get('customer_phone'),
                    'delivery_address': order_data.get('delivery_address'),
                    'city': order_data.get('city'),
                    'zip_code': order_data.get('zip_code'),
                    'items': order_data.get('items'),
                    'special_instructions': order_data.get('special_instructions'),
                    'subtotal': order_data.get('subtotal'),
                    'tax': order_data.get('tax'),
                    'delivery_fee': order_data.get('delivery_fee'),
                    'total_amount': order_data.get('total_amount'),
                    'payment_intent_id': order_data.get('payment_intent_id'),
                    'payment_status': order_data.get('payment_status'),
                    'order_status': order_data.get('order_status'),
                    'created_at': order_data.get('created_at'),
                    'exported_at': datetime.now().isoformat()
                }
                
                # Append new row
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                
                # Save to Excel
                df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')
                
                print(f"✅ Order #{order_data.get('order_id')} exported to Excel")
                
                result['success'] = True
                result['message'] = f"Order #{order_data.get('order_id')} exported successfully"
                result['exported_at'] = new_row['exported_at']
                
            print(f"🔓 Lock released for order #{order_data.get('order_id')}")
                
        except Timeout:
            result['message'] = f"Timeout: Could not acquire lock within {cls.LOCK_TIMEOUT}s"
            print(f"❌ Lock timeout for order #{order_data.get('order_id')}")
            
        except Exception as e:
            result['message'] = f"Error exporting order: {str(e)}"
            print(f"❌ Export error for order #{order_data.get('order_id')}: {e}")
        
        return result
    
    @classmethod
    def get_all_orders(cls) -> list:
        """Read all orders from Excel file"""
        cls._ensure_data_dir()
        
        if not os.path.exists(EXCEL_FILE):
            return []
        
        try:
            df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
            return df.to_dict('records')
        except Exception as e:
            print(f"❌ Error reading Excel: {e}")
            return []
    
    @classmethod
    def get_order_count(cls) -> int:
        """Get total number of orders in Excel"""
        orders = cls.get_all_orders()
        return len(orders)
    
    @classmethod
    def clear_all_orders(cls) -> bool:
        """Delete Excel file (for testing purposes)"""
        try:
            if os.path.exists(EXCEL_FILE):
                os.remove(EXCEL_FILE)
                print("🗑️ Excel file deleted")
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
                print("🗑️ Lock file deleted")
            return True
        except Exception as e:
            print(f"❌ Error clearing files: {e}")
            return False