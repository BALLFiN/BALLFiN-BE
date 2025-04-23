from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv

load_dotenv()

# local mongo
#MONGO_URI = os.getenv("LOCAL_MONGO_URI")
#client = MongoClient(MONGO_URI)

MONGO_URI = os.getenv("ATLAS_MONGO_URI")
# Create a new client and connect to the server
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["BarbellAI"]

user_collection = db["users"]
company_collection = db["companies"]
news_collection = db['news']
disclosure_collection = db['disclosures']

chat_sessions = db["chat_sessions"]
chat_messages = db["chat_messages"]