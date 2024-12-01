import pymongo
import logging
import re
from config import MONGO_URI, SPORTS

# --------------------- Logging Configuration ---------------------
logger = logging.getLogger('UpdateSportsNames')
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)

# --------------------- MongoDB Setup ---------------------
try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client.sports_odds  # Your database name
    moneylines_collection = db.moneylines  # Your collection name
    logger.info("Connected to MongoDB successfully.")
except pymongo.errors.ConnectionError as ce:
    logger.error(f"Failed to connect to MongoDB: {ce}")
    raise ce

# --------------------- Update Sports Names ---------------------
def update_sports_names():
    """
    Updates all sports names in the database to be consistent with config.SPORTS values.
    """
    try:
        # Get all distinct sport names currently in the database
        current_sports = moneylines_collection.distinct('sport')
        logger.info(f"Found sports in database: {current_sports}")
        
        for sport_key, correct_name in SPORTS.items():
            # Create regex patterns for common variations
            sport_parts = sport_key.replace('_', ' ').split()
            patterns = [
                re.compile(correct_name, re.IGNORECASE),  # e.g., "NBA", "nba"
                re.compile(' '.join(sport_parts), re.IGNORECASE),  # e.g., "basketball nba"
                re.compile(''.join(sport_parts), re.IGNORECASE),  # e.g., "basketballnba"
            ]
            
            # Build the query to match any variation
            query = {'sport': {'$in': patterns}}
            
            # Update all matching documents
            result = moneylines_collection.update_many(
                query,
                {'$set': {'sport': correct_name}}
            )
            
            logger.info(f"Updated {result.modified_count} documents for sport: {correct_name}")
            
    except Exception as e:
        logger.error(f"Error updating sports names: {e}")

def main():
    update_sports_names()
    client.close()
    logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    main()