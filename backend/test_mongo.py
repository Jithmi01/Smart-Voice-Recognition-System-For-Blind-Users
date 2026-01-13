from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
print(f"Testing connection to: {uri[:50]}...")

try:
    # Longer timeout for first connection
    client = MongoClient(uri, serverSelectionTimeoutMS=30000)
    client.admin.command('ping')
    print("✅ MongoDB Connection Successful!")
    
    # List databases
    print(f"✅ Available databases: {client.list_database_names()}")
    
    # Test insert
    db = client['voice_recognition_db']
    test_collection = db['test']
    result = test_collection.insert_one({"test": "data"})
    print(f"✅ Test insert successful: {result.inserted_id}")
    
    # Clean up test
    test_collection.delete_one({"test": "data"})
    print("✅ Test cleanup successful")
    
    client.close()
    
except Exception as e:
    print(f"❌ Connection Failed: {e}")
    print("\n💡 Solutions:")
    print("1. Check Network Access → Add IP Address")
    print("2. Wait 2-3 minutes after adding IP")
    print("3. Verify password in .env is correct")
    print("4. Check firewall/antivirus settings")
    print("5. Try different internet connection")