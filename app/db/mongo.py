from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["BarbellAI"]

user_collection = db["users"]
company_collection = db["companies"]
news_collection = db['news']
disclosure_collection = db['disclosures']
