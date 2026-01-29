"""
Excel File Manager with Concurrency Control

Thread-safe Excel operations for:
- Order exports
- Call log exports

Author: Khalil Bannouri
Version: 3.0.0
"""

import os
from datetime import datetime
from typing import Any
from pathlib import Path

import pandas as pd
from filelock import FileLock, Timeout

from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

DATA_DIR = Path(settings.data_directory)
ORDERS_FILE = DATA_DIR / "orders.xlsx"
CALLS_FILE = DATA_DIR / "call_logs.xlsx"
ORDERS_LOCK = DATA_DIR / "orders.xlsx.lock"
CALLS_LOCK = DATA_DIR / "call_logs.xlsx.lock"


class ExcelManager:
    """Thread-safe Excel file manager."""
    
    LOCK_TIMEOUT = settings.excel_lock_timeout
    
    ORDER_COLUMNS = [
        "order_id",
        "order_type",
        "date_time",
        "customer_name",
        "customer_phone",
        "customer_email",
        "customer_language",
        "delivery_address",
        "city",
        "zip_code",
        "pickup_time",
        "items",
        "special_instructions",
        "subtotal",
        "tax",
        "delivery_fee",
        "tip",
        "total_amount",
        "payment_status",
        "payment_intent_id",
        "order_status",
        "call_id",
        "call_transcription",
        "handled_by_ai",
        "transferred_to_human",
        "exported_at",
    ]
    
    CALL_LOG_COLUMNS = [
        "call_id",
        "date_time",
        "caller_phone",
        "caller_language",
        "wanted_to_order",
        "outcome",
        "transcription",
        "recording_url",
        "customer_message",
        "handled_by_ai",
        "transferred_to_human",
        "exported_at",
    ]
    
    @classmethod
    def _ensure_data_dir(cls) -> None:
        """Create data directory if needed."""
        if not DATA_DIR.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created data directory: {DATA_DIR}")
    
    @classmethod
    def _load_or_create_df(cls, file_path: Path, columns: list) -> pd.DataFrame:
        """Load existing file or create new DataFrame."""
        if file_path.exists():
            try:
                return pd.read_excel(file_path, engine="openpyxl")
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
                return pd.DataFrame(columns=columns)
        return pd.DataFrame(columns=columns)
    
    @classmethod
    def export_order(cls, order_data: dict[str, Any]) -> dict[str, Any]:
        """Export order to Excel with file locking."""
        cls._ensure_data_dir()
        
        order_id = order_data.get("order_id", 0)
        result = {
            "success": False,
            "message": "",
            "order_id": order_id,
            "exported_at": None,
        }
        
        try:
            lock = FileLock(str(ORDERS_LOCK), timeout=cls.LOCK_TIMEOUT)
            
            with lock:
                logger.debug(f"Lock acquired for Order #{order_id}")
                
                df = cls._load_or_create_df(ORDERS_FILE, cls.ORDER_COLUMNS)
                
                export_time = datetime.now().isoformat()
                new_row = {
                    "order_id": order_id,
                    "order_type": order_data.get("order_type", "delivery"),
                    "date_time": order_data.get("created_at", export_time),
                    "customer_name": order_data.get("customer_name"),
                    "customer_phone": order_data.get("customer_phone"),
                    "customer_email": order_data.get("customer_email"),
                    "customer_language": order_data.get("customer_language", "en"),
                    "delivery_address": order_data.get("delivery_address"),
                    "city": order_data.get("city"),
                    "zip_code": order_data.get("zip_code"),
                    "pickup_time": order_data.get("pickup_time"),
                    "items": order_data.get("items"),
                    "special_instructions": order_data.get("special_instructions"),
                    "subtotal": order_data.get("subtotal"),
                    "tax": order_data.get("tax"),
                    "delivery_fee": order_data.get("delivery_fee"),
                    "tip": order_data.get("tip", 0),
                    "total_amount": order_data.get("total_amount"),
                    "payment_status": order_data.get("payment_status"),
                    "payment_intent_id": order_data.get("payment_intent_id"),
                    "order_status": order_data.get("order_status"),
                    "call_id": order_data.get("call_id"),
                    "call_transcription": order_data.get("call_transcription"),
                    "handled_by_ai": order_data.get("handled_by_ai", True),
                    "transferred_to_human": order_data.get("transferred_to_human", False),
                    "exported_at": export_time,
                }
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_excel(str(ORDERS_FILE), index=False, engine="openpyxl")
                
                logger.info(f"Order #{order_id} exported to Excel")
                
                result["success"] = True
                result["message"] = f"Order #{order_id} exported"
                result["exported_at"] = export_time
            
            logger.debug(f"Lock released for Order #{order_id}")
            
        except Timeout:
            result["message"] = f"Lock timeout ({cls.LOCK_TIMEOUT}s)"
            logger.error(f"Lock timeout for Order #{order_id}")
            
        except Exception as e:
            result["message"] = str(e)
            logger.exception(f"Error exporting Order #{order_id}")
        
        return result
    
    @classmethod
    def export_call_log(cls, call_data: dict[str, Any]) -> dict[str, Any]:
        """Export call log to Excel with file locking."""
        cls._ensure_data_dir()
        
        call_id = call_data.get("call_id", "unknown")
        result = {
            "success": False,
            "message": "",
            "call_id": call_id,
            "exported_at": None,
        }
        
        try:
            lock = FileLock(str(CALLS_LOCK), timeout=cls.LOCK_TIMEOUT)
            
            with lock:
                logger.debug(f"Lock acquired for Call {call_id}")
                
                df = cls._load_or_create_df(CALLS_FILE, cls.CALL_LOG_COLUMNS)
                
                export_time = datetime.now().isoformat()
                new_row = {
                    "call_id": call_id,
                    "date_time": call_data.get("created_at", export_time),
                    "caller_phone": call_data.get("caller_phone"),
                    "caller_language": call_data.get("caller_language", "en"),
                    "wanted_to_order": call_data.get("wanted_to_order", False),
                    "outcome": call_data.get("outcome", "no_order"),
                    "transcription": call_data.get("transcription"),
                    "recording_url": call_data.get("recording_url"),
                    "customer_message": call_data.get("customer_message"),
                    "handled_by_ai": call_data.get("handled_by_ai", True),
                    "transferred_to_human": call_data.get("transferred_to_human", False),
                    "exported_at": export_time,
                }
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_excel(str(CALLS_FILE), index=False, engine="openpyxl")
                
                logger.info(f"Call {call_id} exported to Excel")
                
                result["success"] = True
                result["message"] = f"Call {call_id} exported"
                result["exported_at"] = export_time
            
            logger.debug(f"Lock released for Call {call_id}")
            
        except Timeout:
            result["message"] = f"Lock timeout ({cls.LOCK_TIMEOUT}s)"
            logger.error(f"Lock timeout for Call {call_id}")
            
        except Exception as e:
            result["message"] = str(e)
            logger.exception(f"Error exporting Call {call_id}")
        
        return result
    
    @classmethod
    def get_all_orders(cls) -> list[dict[str, Any]]:
        """Get all orders from Excel."""
        cls._ensure_data_dir()
        
        if not ORDERS_FILE.exists():
            return []
        
        try:
            df = pd.read_excel(ORDERS_FILE, engine="openpyxl")
            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Error reading orders: {e}")
            return []
    
    @classmethod
    def get_all_call_logs(cls) -> list[dict[str, Any]]:
        """Get all call logs from Excel."""
        cls._ensure_data_dir()
        
        if not CALLS_FILE.exists():
            return []
        
        try:
            df = pd.read_excel(CALLS_FILE, engine="openpyxl")
            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Error reading call logs: {e}")
            return []
    
    @classmethod
    def clear_all(cls) -> bool:
        """Delete all Excel files."""
        try:
            for f in [ORDERS_FILE, CALLS_FILE, ORDERS_LOCK, CALLS_LOCK]:
                if f.exists():
                    f.unlink()
            logger.info("All Excel files cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing files: {e}")
            return False