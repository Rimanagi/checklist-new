from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_DETAILS = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.my_database

locations_collection = database.get_collection("locations")
checklists_collection = database.get_collection("checklists")
users_collection = database.get_collection("users")
passwords_collection = database.get_collection("passwords")
