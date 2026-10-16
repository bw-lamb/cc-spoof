#!/usr/bin/env python3

import random
from datetime import datetime, timedelta
from decimal import Decimal
from faker import Faker
from pymongo import MongoClient
from bson import ObjectId, Decimal128

# Initialize Faker
fake = Faker()

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "globalcard2"
BATCH_SIZE = 5000  

# Scale parameters (Adjust as needed for your pipeline size)
TOTAL_MERCHANTS = 10000
TOTAL_ACCOUNTS = 100000
MIN_TX_PER_ACCOUNT = 40
MAX_TX_PER_ACCOUNT = 150

# Strict transaction type distribution ratios
TX_TYPES = ["PURCHASE", "FEE", "PAYMENT", "ADVANCE", "ADJUSTMENT"]
TX_WEIGHTS = [0.84,       0.05,  0.07,      0.03,      0.01] 

# ---------------------------------------------------------
# CORE MOCK GENERATORS
# ---------------------------------------------------------
def generate_object_id() -> ObjectId:
    return ObjectId()

def generate_bigint() -> int:
    return fake.random_number(digits=15, fix_len=True)

def generate_decimal128(min_val: float, max_val: float) -> Decimal128:
    val = round(random.uniform(min_val, max_val), 2)
    return Decimal128(Decimal(str(val)))

def generate_digit_tuple(length: int) -> list:
    return [fake.random_digit() for _ in range(length)]

# ---------------------------------------------------------
# RELATIONAL MERCHANT POOL (WITH WEIGHTED MARKET SHARE)
# ---------------------------------------------------------
def generate_merchant_pool(total_merchants: int):
    """
    Generates a pool of merchants where a few global giants dominate 
    the market share distribution, while others act as small boutique stores.
    """
    merchants = []
    locations = []
    
    # Pre-defined high market share retailers (with valid DigitTuple lists for MCC codes)
    mega_merchants = [
        {"name": "Amazon.com", "weight": 25.0, "mcc": [4, 8, 1, 1], "locations_count": 1},
        {"name": "Walmart Supercenter", "weight": 18.0, "mcc": [5, 4, 1, 1], "locations_count": 15},
        {"name": "Target Stores", "weight": 8.0, "mcc": [5, 3, 1, 0], "locations_count": 8},
        {"name": "Costco Wholesale", "weight": 7.0, "mcc": [5, 3, 0, 0], "locations_count": 5},
        {"name": "Apple Store", "weight": 5.0, "mcc": [5, 7, 3, 2], "locations_count": 3},
    ]
    
    # 1. Populate Mega Giants
    for mega in mega_merchants:
        m_id = generate_bigint()
        merchant_doc = {
            "_id": generate_object_id(),
            "merchantId": m_id,
            "name": mega["name"],
            "mccCode": mega["mcc"],
            "creationDate": fake.date_time_between(start_date="-25y", end_date="-15y")
        }
        merchants.append((merchant_doc, mega["weight"]))
        
        for i in range(mega["locations_count"]):
            locations.append({
                "_id": generate_object_id(),
                "merchantId": m_id,
                "address": fake.street_address(),
                "locationName": f"{mega['name']} - Hub #{i+1}" if mega['locations_count'] > 1 else f"{mega['name']} Corporate Hub",
                "postalCode": fake.postcode(),
                "countryCode": "US",
                "isActive": True
            })

    # 2. Populate Long-Tail Small/Medium Merchants
    remaining_slots = total_merchants - len(mega_merchants)
    for _ in range(remaining_slots):
        m_id = generate_bigint()
        
        tier = random.choices(["MEDIUM", "SMALL"], weights=[0.03, 0.97], k=1)[0]
        if tier == "MEDIUM":
            weight = random.uniform(0.1, 0.5)
            loc_count = random.randint(2, 4)
        else:
            weight = random.uniform(0.005, 0.04)
            loc_count = 1
            
        merchant_doc = {
            "_id": generate_object_id(),
            "merchantId": m_id,
            "name": fake.company(),
            "mccCode": generate_digit_tuple(4),
            "creationDate": fake.date_time_between(start_date="-10y", end_date="-1y")
        }
        merchants.append((merchant_doc, weight))
        
        for _ in range(loc_count):
            locations.append({
                "_id": generate_object_id(),
                "merchantId": m_id,
                "address": fake.street_address(),
                "locationName": fake.city() + " Branch",
                "postalCode": fake.postcode(),
                "countryCode": fake.country_code(representation="alpha-2"),
                "isActive": True
            })
            
    return merchants, locations

# ---------------------------------------------------------
# ACCOUNT & CARD CORE BUILDERS
# ---------------------------------------------------------
def create_cardholder() -> dict:
    return {
        "_id": generate_object_id(),
        "name": {"first": fake.first_name(), "last": fake.last_name()},
        "billingAddress": fake.address().replace("\n", ", "),
        "shippingAddress": fake.address().replace("\n", ", ")
    }

def create_account() -> dict:
    creation_date = fake.date_time_between(start_date="-4y", end_date="-1y")
    credit_limit = generate_decimal128(5000.00, 35000.00)
    current_balance = generate_decimal128(0.00, float(credit_limit.to_decimal()) * 0.4)
    
    # Fixed target arrays inside choices extraction
    num_holders = random.choices([1, 2], weights=[0.88, 0.12], k=1)[0]
    return {
        "_id": generate_object_id(),
        "accountId": generate_bigint(),
        "currentBalance": current_balance,
        "creditLimit": credit_limit,
        "creationDate": creation_date,
        "cardholders": [create_cardholder() for _ in range(num_holders)]
    }

def create_card(account_id: int, cardholder: dict) -> dict:
    start_date = fake.date_time_between(start_date="-2y", end_date="now")
    status_choice = random.choices(["ACTIVE", "SUSPENDED", "EXPIRED"], weights=[0.94, 0.03, 0.03], k=1)[0]
    return {
        "_id": generate_object_id(),
        "accountId": account_id,
        "cardholder": cardholder,
        "vaultToken": generate_bigint(),
        "lastFourDigits": generate_digit_tuple(4),
        "status": status_choice,
        "startDate": start_date,
        "endDate": start_date + timedelta(days=365 * 4),
        "activationDate": start_date + timedelta(hours=random.randint(1, 12))
    }

# ---------------------------------------------------------
# HIGH PERFORMANCE STREAMING ENGINE
# ---------------------------------------------------------
def run_pipeline():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print(f"Purging old schemas in database '{DB_NAME}'...")
    db.merchants.drop()
    db.merchant_locations.drop()
    db.accounts.drop()
    db.cards.drop()
    db.transactions.drop()
    
    # 1. Setup Weighted Merchant Pools
    print(f"Generating {TOTAL_MERCHANTS} structural merchants based on Pareto Distribution...")
    raw_merchants, merchant_locations = generate_merchant_pool(TOTAL_MERCHANTS)
    
    # Safely unpack the tuple pairs using direct list indices
    merchant_docs = [m[0] for m in raw_merchants]
    merchant_ids = [m[0]["merchantId"] for m in raw_merchants]
    merchant_weights = [m[1] for m in raw_merchants]
    
    db.merchants.insert_many(merchant_docs)
    db.merchant_locations.insert_many(merchant_locations)
    print(f"Successfully cached and stored {len(merchant_docs)} unique merchant profiles.")
    
    del merchant_locations  # Free unneeded items from RAM
    
    # 2. Main Streaming Engine
    print(f"Streaming {TOTAL_ACCOUNTS} accounts along with associated nested items...")
    accounts_buf, cards_buf, tx_buf = [], [], []
    total_tx_counter = 0
    
    for i in range(1, TOTAL_ACCOUNTS + 1):
        account = create_account()
        accounts_buf.append(account)
        
        for ch in account["cardholders"]:
            cards_buf.append(create_card(account["accountId"], ch))
            
        num_transactions = random.randint(MIN_TX_PER_ACCOUNT, MAX_TX_PER_ACCOUNT)
        assigned_types = random.choices(TX_TYPES, weights=TX_WEIGHTS, k=num_transactions)
        
        for tx_type in assigned_types:
            tx_date = fake.date_time_between(start_date="-1y", end_date="now")
            is_disp = random.choices([True, False], weights=[0.008, 0.992], k=1)[0]
            
            base_tx = {
                "_id": generate_object_id(),
                "accountId": account["accountId"],
                "transactionId": generate_bigint(),
                "transactionType": tx_type,
                "transactionDate": tx_date,
                "postedDate": tx_date + timedelta(days=random.randint(1, 2)),
                "amount": generate_decimal128(4.50, 650.00),
                "isDisputed": is_disp
            }
            
            if tx_type == "PURCHASE":
                # Clean list extraction via index mapping [0] prevents duplicate key clustering
                m_id = random.choices(merchant_ids, weights=merchant_weights, k=1)[0]
                is_recur = random.choices([True, False], weights=[0.08, 0.92], k=1)[0]
                base_tx.update({
                    "merchantId": m_id,
                    "terminalId": generate_bigint(),
                    "authCode": generate_digit_tuple(6),
                    "isRecurring": is_recur
                })
                # Check for subsequent refund event scenarios
                if random.random() < 0.06:
                    refund_date = tx_date + timedelta(days=random.randint(1, 10))
                    tx_buf.append({
                        "_id": generate_object_id(),
                        "accountId": account["accountId"],
                        "transactionId": generate_bigint(),
                        "transactionType": "REFUND",
                        "transactionDate": refund_date,
                        "postedDate": refund_date + timedelta(days=1),
                        "amount": base_tx["amount"],
                        "isDisputed": False,
                        "originalPurchaseId": base_tx["transactionId"],
                        "merchantId": m_id,
                        "isChargebackDisputed": False
                    })
                    total_tx_counter += 1
            elif tx_type == "FEE":
                base_tx["amount"] = generate_decimal128(1.50, 45.00)
            elif tx_type == "PAYMENT":
                base_tx.update({
                    "method": random.choice(["ACH", "DEBIT"]),
                    "routingNumber": fake.random_number(digits=9, fix_len=True),
                    "accountNumber": fake.random_number(digits=10, fix_len=True)
                })
            elif tx_type == "ADVANCE":
                base_tx.update({"atmId": generate_bigint(), "feeApplied": "$3.50"})
            elif tx_type == "ADJUSTMENT":
                base_tx.update({
                    "reason": random.choice(["Waived Fee", "Promo Credit"]),
                    "authorizedByEmployee": True,
                    "impactDirection": random.choice(["D", "C"])
                })

            tx_buf.append(base_tx)
            total_tx_counter += 1

            # Flush buffers safely at set intervals
            if len(accounts_buf) >= BATCH_SIZE:
                db.accounts.insert_many(accounts_buf)
                accounts_buf.clear()
            if len(cards_buf) >= BATCH_SIZE:
                db.cards.insert_many(cards_buf)
                cards_buf.clear()
            if len(tx_buf) >= BATCH_SIZE:
                db.transactions.insert_many(tx_buf)          
                tx_buf.clear()

        if i % 2500 == 0:
            print(f"Staged {i}/{TOTAL_ACCOUNTS} accounts... Total transactions created: {total_tx_counter}")

    # Process outstanding elements remaining in queues
    if accounts_buf: db.accounts.insert_many(accounts_buf)
    if cards_buf: db.cards.insert_many(cards_buf)
    if tx_buf: db.transactions.insert_many(tx_buf)

    print("\n--- Pipeline Completed Successfully ---")
    print(f"Total Accounts Created: {db.accounts.count_documents({})}")
    print(f"Total Cards Created: {db.cards.count_documents({})}")
    print(f"Total Transactions Created: {db.transactions.count_documents({})}")

if __name__ == "__main__":
    run_pipeline()
