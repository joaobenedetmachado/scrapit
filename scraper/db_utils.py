import os
from pymongo import MongoClient
from dotenv import load_dotenv
from pymongo.errors import PyMongoError
import re
from scraper.logger import log

load_dotenv()

uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DATABASE")
collection_name = os.getenv("MONGO_COLLECTION")

client = MongoClient(uri)

db = client[db_name]
collection = db[collection_name]

collection.insert_one({"test": True})

def save_scraped(data):
    if not isinstance(data, dict):
        raise TypeError(
            f"save_scraped recebeu tipo inválido: {type(data)}\nConteúdo: {data}"
        )

    try:
        result = collection.insert_one(data)
        return "added to database" 
    except Exception as e:
        log(f"error inserting in database: {e}")
        return "error in storage"

def get_elements_by_site(name):
    escaped = re.escape(name)
    pattern = re.compile(rf"^{escaped}", re.IGNORECASE)
    return list(collection.find({ "url": pattern }))

def get_elements_by_part(name, part):
    try:
        escaped = re.escape(name)
        pattern = re.compile(rf"^{escaped}", re.IGNORECASE)
        log(f"Getting elements by part: {part}")
        return list(collection.find({ f"{part}": pattern }))
    except Exception as e:
        log(f"error getting elements by part: {e}")
        return "error in storage"

def change_db(info):
    pass