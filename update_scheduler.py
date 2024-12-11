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
UPDATE_DELAY_HOURS = 3

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
START_TIME = datetime.now(PST_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
END_TIME = datetime.now(PST_TZ).replace(hour=23, minute=59, second=59, microsecond=0)
UPDATE_INTERVAL_HOURS = 4  # Changed from 2 to 4 hours

def get_update_times():
    """
    Get the times to run updates based on first and last game times.
    Returns tuple of (first_update_time, last_update_time) in PST.
    """
    try:
        today = datetime.now(PST_TZ).date()
        today_start = datetime.combine(today, datetime.min.time())
        today_start = PST_TZ.localize(today_start)
        today_end = today_start + timedelta(days=1)

        # Query for today's games
        games = list(moneylines_collection.find({
            'event_date': {
                '$gte': today_start,
                '$lt': today_end
            }
        }).sort('event_date', 1))  # Sort by event_date ascending

        if not games:
            logger.info("No games found for today.")
            return None, None

        # Get first and last game times
        first_game = games[0]['event_date']
        last_game = games[-1]['event_date']

        # Convert to PST if they're not already
        if first_game.tzinfo is None:
            first_game = pytz.utc.localize(first_game)
        if last_game.tzinfo is None:
            last_game = pytz.utc.localize(last_game)

        first_game_pst = first_game.astimezone(PST_TZ)
        last_game_pst = last_game.astimezone(PST_TZ)

        # Add delay for updates
        first_update = first_game_pst + timedelta(hours=UPDATE_DELAY_HOURS)
        last_update = last_game_pst + timedelta(hours=UPDATE_DELAY_HOURS)

        logger.info(f"First game time (PST): {first_game_pst}")
        logger.info(f"Last game time (PST): {last_game_pst}")
        logger.info(f"First update time (PST): {first_update}")
        logger.info(f"Last update time (PST): {last_update}")

        return first_update, last_update

    except Exception as e:
        logger.error(f"Error getting update times: {e}")
        return None, None

def is_update_time():
    """
    Determines if current time is within 5 minutes of a scheduled update.
    Updates occur every 4 hours between 12 PM and 12 AM PST.
    """
    try:
        now = datetime.now(PST_TZ)
        if not (START_TIME.time() <= now.time() <= END_TIME.time()):
            return False

        # Calculate hours since start of window
        hours_since_start = (now - now.replace(hour=12, minute=0, second=0, microsecond=0)).total_seconds() / 3600
        
        # Check if we're within 5 minutes of a scheduled update
        minutes_since_last_update = (hours_since_start % UPDATE_INTERVAL_HOURS) * 60
        return minutes_since_last_update <= 5 or minutes_since_last_update >= (UPDATE_INTERVAL_HOURS * 60 - 5)

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
