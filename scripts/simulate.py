"""
Chaos Simulation Script

Simulates high-concurrency order flow to test system resilience.
Run from project root: python scripts/simulate.py

Author: Khalil_Bannouri
Version: 1.0.0
"""

import asyncio
import sys
import os
import random
import time
import argparse
from datetime import datetime
from typing import Any

import httpx
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Windows event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configuration
API_BASE_URL = "http://localhost:8001"
TOTAL_ORDERS = 50

# Sample data for random orders
FIRST_NAMES = ["John", "Jane", "Mike", "Sarah", "Tom", "Emma", "David", "Lisa", "Chris", "Amy"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Taylor"]
STREETS = ["Main St", "Broadway", "5th Avenue", "Park Ave", "Madison Ave", "Lexington Ave", "Amsterdam Ave"]
VALID_ZIPS = ["10001", "10002", "10003", "10004", "10005", "10006", "10007", "10008", "10009", "10010"]
MENU_ITEMS = [
    {"name": "Pizza Margherita", "unit_price": 14.99},
    {"name": "Pepperoni Pizza", "unit_price": 16.99},
    {"name": "Caesar Salad", "unit_price": 8.99},
    {"name": "Garlic Bread", "unit_price": 5.99},
    {"name": "Pasta Carbonara", "unit_price": 13.99},
    {"name": "Tiramisu", "unit_price": 7.99},
    {"name": "Coke", "unit_price": 2.99},
    {"name": "Sparkling Water", "unit_price": 3.49},
]


def generate_random_customer() -> dict[str, str]:
    """Generate random customer info."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return {
        "name": f"{first} {last}",
        "phone": f"555-{random.randint(100,999)}-{random.randint(1000,9999)}",
        "address": f"{random.randint(1, 999)} {random.choice(STREETS)}",
        "city": "New York",
        "zip_code": random.choice(VALID_ZIPS),
    }


def generate_random_items() -> list[dict]:
    """Generate random order items."""
    num_items = random.randint(1, 4)
    items = []
    for _ in range(num_items):
        item = random.choice(MENU_ITEMS).copy()
        item["quantity"] = random.randint(1, 3)
        items.append(item)
    return items


# =============================================================================
# DIRECT API SIMULATION
# =============================================================================

def generate_direct_api_payload() -> dict[str, Any]:
    """Generate payload for /api/orders endpoint."""
    customer = generate_random_customer()
    items = generate_random_items()
    
    return {
        "customer_name": customer["name"],
        "customer_phone": customer["phone"],
        "delivery_address": customer["address"],
        "city": customer["city"],
        "zip_code": customer["zip_code"],
        "items": items,
        "special_instructions": random.choice([
            None, "Extra napkins", "Ring doorbell", "Leave at door", "Call on arrival"
        ]),
        "card_last_four": "4242"
    }


async def send_direct_order(
    client: httpx.AsyncClient,
    order_num: int
) -> dict[str, Any]:
    """Send order via direct API."""
    payload = generate_direct_api_payload()
    start_time = time.time()
    
    try:
        response = await client.post(
            f"{API_BASE_URL}/api/orders",
            json=payload,
            timeout=30.0
        )
        elapsed = round(time.time() - start_time, 3)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "order_num": order_num,
                "success": True,
                "order_id": data.get("order_id"),
                "total": data.get("total_amount"),
                "time": elapsed,
                "mode": "direct"
            }
        else:
            return {
                "order_num": order_num,
                "success": False,
                "error": response.text[:100],
                "time": elapsed,
                "mode": "direct"
            }
    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        return {
            "order_num": order_num,
            "success": False,
            "error": str(e)[:100],
            "time": elapsed,
            "mode": "direct"
        }


# =============================================================================
# VAPI SIMULATION
# =============================================================================

def generate_vapi_create_order_payload() -> dict[str, Any]:
    """Generate Vapi-style webhook payload for order creation."""
    customer = generate_random_customer()
    items = generate_random_items()
    
    # Calculate total for payment
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    tax = round(subtotal * 0.08875, 2)
    delivery_fee = 5.99
    total = round(subtotal + tax + delivery_fee, 2)
    
    return {
        "type": "function-call",
        "functionCall": {
            "name": "create_order",
            "parameters": {
                "customer_name": customer["name"],
                "customer_phone": customer["phone"],
                "delivery_address": customer["address"],
                "city": customer["city"],
                "zip_code": customer["zip_code"],
                "items": items,
                "special_instructions": random.choice([
                    None, "Extra cheese", "No onions", "Spicy"
                ]),
                "payment_id": f"pi_mock_{random.randint(100000, 999999)}",
            }
        },
        "call": {
            "id": f"call_{random.randint(100000, 999999)}",
            "customer": {
                "number": customer["phone"]
            }
        }
    }


async def send_vapi_order(
    client: httpx.AsyncClient,
    order_num: int
) -> dict[str, Any]:
    """Send order via Vapi simulation endpoint."""
    payload = generate_vapi_create_order_payload()
    start_time = time.time()
    
    try:
        response = await client.post(
            f"{API_BASE_URL}/webhook/simulation",
            json=payload,
            timeout=30.0
        )
        elapsed = round(time.time() - start_time, 3)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("result", {})
            
            if result.get("success"):
                return {
                    "order_num": order_num,
                    "success": True,
                    "order_id": result.get("order_id"),
                    "total": result.get("total_amount"),
                    "time": elapsed,
                    "mode": "vapi"
                }
            else:
                return {
                    "order_num": order_num,
                    "success": False,
                    "error": result.get("message", "Unknown error")[:100],
                    "time": elapsed,
                    "mode": "vapi"
                }
        else:
            return {
                "order_num": order_num,
                "success": False,
                "error": response.text[:100],
                "time": elapsed,
                "mode": "vapi"
            }
    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        return {
            "order_num": order_num,
            "success": False,
            "error": str(e)[:100],
            "time": elapsed,
            "mode": "vapi"
        }


# =============================================================================
# MAIN SIMULATION RUNNER
# =============================================================================

async def run_simulation(
    mode: str = "both",
    num_orders: int = TOTAL_ORDERS
) -> dict[str, Any]:
    """
    Run the chaos simulation.
    
    Args:
        mode: "direct", "vapi", or "both"
        num_orders: Number of orders to simulate
    """
    print("=" * 70)
    print("🔥 CHAOS SIMULATION - HIGH CONCURRENCY TEST")
    print("=" * 70)
    print(f"📋 Total Orders: {num_orders}")
    print(f"🎯 Target: {API_BASE_URL}")
    print(f"🔧 Mode: {mode}")
    print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)
    
    results = []
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        if mode == "direct":
            print("\n🚀 Firing Direct API orders...\n")
            tasks = [send_direct_order(client, i+1) for i in range(num_orders)]
            results = await asyncio.gather(*tasks)
            
        elif mode == "vapi":
            print("\n🚀 Firing Vapi Simulation orders...\n")
            tasks = [send_vapi_order(client, i+1) for i in range(num_orders)]
            results = await asyncio.gather(*tasks)
            
        else:  # both
            print("\n🚀 Firing Mixed orders (Direct + Vapi)...\n")
            tasks = []
            for i in range(num_orders):
                if i % 2 == 0:
                    tasks.append(send_direct_order(client, i+1))
                else:
                    tasks.append(send_vapi_order(client, i+1))
            results = await asyncio.gather(*tasks)
    
    total_time = round(time.time() - start_time, 2)
    
    # Analyze results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    direct_results = [r for r in results if r.get("mode") == "direct"]
    vapi_results = [r for r in results if r.get("mode") == "vapi"]
    
    # Print results
    print("\n" + "=" * 70)
    print("📊 SIMULATION RESULTS")
    print("=" * 70)
    
    print(f"\n✅ Successful Orders: {len(successful)}/{num_orders}")
    print(f"❌ Failed Orders: {len(failed)}/{num_orders}")
    print(f"⏱️  Total Time: {total_time}s")
    
    if direct_results:
        direct_success = len([r for r in direct_results if r["success"]])
        print(f"\n📡 Direct API: {direct_success}/{len(direct_results)} successful")
    
    if vapi_results:
        vapi_success = len([r for r in vapi_results if r["success"]])
        print(f"🎤 Vapi Simulation: {vapi_success}/{len(vapi_results)} successful")
    
    if successful:
        avg_time = round(sum(r["time"] for r in successful) / len(successful), 3)
        min_time = min(r["time"] for r in successful)
        max_time = max(r["time"] for r in successful)
        total_revenue = sum(r.get("total", 0) for r in successful)
        
        print(f"\n📈 Performance Metrics:")
        print(f"   Average Response: {avg_time}s")
        print(f"   Fastest: {min_time}s")
        print(f"   Slowest: {max_time}s")
        print(f"   💰 Total Revenue: ${total_revenue:.2f}")
    
    if failed:
        print(f"\n⚠️  Failed Order Details (showing first 5):")
        for f in failed[:5]:
            print(f"   Order #{f['order_num']} [{f.get('mode', 'unknown')}]: {f.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    print("🔍 VERIFICATION STEPS")
    print("=" * 70)
    print("1. Check Celery terminal - all tasks should complete")
    print("2. Run: python verify_excel.py")
    print("3. Open data/orders.xlsx to verify data integrity")
    print("4. Visit http://localhost:8001/dashboard to see results")
    print("=" * 70)
    
    return {
        "total": num_orders,
        "successful": len(successful),
        "failed": len(failed),
        "total_time": total_time,
        "results": results
    }


async def test_single_flows():
    """Test individual flows before chaos simulation."""
    print("\n" + "=" * 70)
    print("🧪 TESTING INDIVIDUAL FLOWS")
    print("=" * 70)
    
    async with httpx.AsyncClient() as client:
        # Test 1: Health check
        print("\n1️⃣ Health Check...")
        response = await client.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {data.get('status')}")
            print(f"   Database: {data.get('database')}")
            print(f"   Redis: {data.get('redis')}")
        else:
            print(f"   ❌ Failed: {response.text}")
            return False
        
        # Test 2: Vapi address check
        print("\n2️⃣ Vapi Address Validation...")
        response = await client.post(
            f"{API_BASE_URL}/webhook/simulation",
            json={
                "type": "function-call",
                "functionCall": {
                    "name": "check_delivery_address",
                    "parameters": {
                        "address": "350 Fifth Avenue",
                        "city": "New York",
                        "zip_code": "10001"
                    }
                },
                "call": {"id": "test_123"}
            }
        )
        if response.status_code == 200:
            result = response.json().get("result", {})
            print(f"   ✅ Valid: {result.get('success')}")
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   ❌ Failed: {response.text}")
        
        # Test 3: Single direct order
        print("\n3️⃣ Single Direct API Order...")
        response = await client.post(
            f"{API_BASE_URL}/api/orders",
            json=generate_direct_api_payload()
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Order #{data.get('order_id')} created")
            print(f"   Total: ${data.get('total_amount')}")
        else:
            print(f"   ⚠️ Response: {response.text[:100]}")
        
        # Test 4: Single Vapi order
        print("\n4️⃣ Single Vapi Simulation Order...")
        response = await client.post(
            f"{API_BASE_URL}/webhook/simulation",
            json=generate_vapi_create_order_payload()
        )
        if response.status_code == 200:
            result = response.json().get("result", {})
            if result.get("success"):
                print(f"   ✅ Order #{result.get('order_id')} created")
                print(f"   Total: ${result.get('total_amount')}")
            else:
                print(f"   ⚠️ Message: {result.get('message')}")
        else:
            print(f"   ❌ Failed: {response.text}")
    
    print("\n" + "=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chaos Simulation Script")
    parser.add_argument("--direct", action="store_true", help="Direct API mode only")
    parser.add_argument("--vapi", action="store_true", help="Vapi simulation mode only")
    parser.add_argument("--orders", type=int, default=50, help="Number of orders")
    parser.add_argument("--skip-tests", action="store_true", help="Skip individual tests")
    args = parser.parse_args()
    
    # Determine mode
    if args.direct:
        mode = "direct"
    elif args.vapi:
        mode = "vapi"
    else:
        mode = "both"
    
    # Run tests first
    if not args.skip_tests:
        success = asyncio.run(test_single_flows())
        if not success:
            print("\n❌ Pre-flight tests failed. Fix issues before running simulation.")
            sys.exit(1)
        
        print("\n✅ Pre-flight tests passed!")
        input("\nPress Enter to start chaos simulation...")
    
    # Run simulation
    asyncio.run(run_simulation(mode=mode, num_orders=args.orders))