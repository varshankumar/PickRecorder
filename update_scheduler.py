import os
import subprocess
from datetime import datetime, timedelta
import pytz
import pymongo
from config import MONGO_URI
import logging

# --------------------- Logging Configuration ---------------------
logger = logging.getLogger('UpdateScheduler')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Constants
PST_TZ = pytz.timezone('America/Los_Angeles')

# MongoDB Setup
try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client.sports_odds
    moneylines_collection = db.moneylines
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise e

# Update Constants
PST_TZ = pytz.timezone('America/Los_Angeles')
UPDATE_TIMES = [
    (13, 0),  # 1 PM
    (20, 0),  # 8 PM
    (0, 0)    # 12 AM (midnight)
]

def is_update_time():
    """
    Determines if current time is within 5 minutes of scheduled updates at 1 PM, 8 PM, and 12 AM PST.
    """
    try:
        now = datetime.now(PST_TZ)
        
        for hour, minute in UPDATE_TIMES:
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            time_diff = abs((now - scheduled_time).total_seconds() / 60)
            
            if time_diff <= 30:  # Within 5 minutes of scheduled time
                return True
        
        return False

    except Exception as e:
        logger.error(f"Error checking update time: {e}")
        return False

def run_update_game_results():
    """
    Executes the update_game_results.py script.
    """
    try:
        logger.info("Running update_game_results.py...")
        subprocess.run(["python", "update_game_results.py"], check=True)
        logger.info("update_game_results.py completed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running update_game_results.py: {e}")

def main():
    if is_update_time():
        logger.info("Update window active. Proceeding to update game results...")
        run_update_game_results()
    else:
        logger.info("Outside update window. Skipping update.")

if __name__ == "__main__":
    main()
