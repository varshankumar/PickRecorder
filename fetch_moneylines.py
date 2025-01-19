import json
import logging
from datetime import datetime, timezone, timedelta
import time

import pymongo
import requests

from config import (
    MONGO_URI,
    ODDS_API_KEY,
    API_BASE_URL,
    SPORTS,
    REGION,
    MARKET,
    ODDS_FORMAT,
    DATE_FORMAT
)

# --------------------- Logging Configuration ---------------------
logger = logging.getLogger('FetchMoneylines')
logger.setLevel(logging.INFO)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handlers to the logger
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

# --------------------- Fetching Odds Data ---------------------
def fetch_moneyline_odds(sport_key):
    """
    Fetches moneyline odds for a specific sport from The Odds API.
    Now includes all available future games.
    """
    url = f"{API_BASE_URL}{sport_key}/odds"
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': REGION,
        'markets': MARKET,
        'oddsFormat': ODDS_FORMAT,
        'dateFormat': DATE_FORMAT,
        'bookmakers': 'draftkings',  # Add a major bookmaker for consistency
        'eventIds': None  # This tells the API to return all available events
    }

    try:
        logger.info(f"Fetching odds for {SPORTS.get(sport_key)} including future games")
        response = requests.get(url, params=params)
        response.raise_for_status()
        odds_data = response.json()

        # Log the full API response
        logger.info(f"Full API response for {sport_key}: {odds_data}")

        # Log the games being fetched
        for game in odds_data:
            logger.info(f"Fetched game: {game.get('sport_title')} - {game.get('commence_time')} - {game.get('home_team')} vs {game.get('away_team')}")
        
        return odds_data
    except Exception as e:
        logger.error(f"Error fetching odds: {e}")
        return []

# --------------------- Processing and Storing Data ---------------------
def process_and_store_odds(odds_data, sport_key):
    """
    Processes odds data and stores it in MongoDB.
    Modified to handle future games better.
    """
    operations = []
    current_time = datetime.now(timezone.utc)

    for event in odds_data:
        try:
            # Basic validation
            game_id = event.get('id')
            commence_time_str = event.get('commence_time')
            
            if not all([game_id, commence_time_str]):
                continue
                
            # Parse the commence time
            commence_time = datetime.strptime(
                commence_time_str, 
                '%Y-%m-%dT%H:%M:%SZ'
            ).replace(tzinfo=timezone.utc)
            
            home_team = event.get('home_team')
            away_team = event.get('away_team')
            bookmakers = event.get('bookmakers', [])

            if not all([home_team, away_team, bookmakers]):
                logger.warning(f"Incomplete data for event ID {game_id}. Skipping. Full event data: {event}")
                continue

            # Initialize moneyline variables
            home_moneyline = None
            away_moneyline = None

            # Iterate through bookmakers to find moneyline odds
            for bookmaker in bookmakers:
                markets = bookmaker.get('markets', [])
                for market in markets:
                    if market.get('key') == 'h2h':
                        outcomes = market.get('outcomes', [])
                        for outcome in outcomes:
                            team = outcome.get('name')
                            price = outcome.get('price')
                            if team == home_team:
                                home_moneyline = price
                            elif team == away_team:
                                away_moneyline = price

            if home_moneyline is None or away_moneyline is None:
                logger.warning(f"Missing moneyline odds for event ID {game_id}. Skipping.")
                continue

            # Prepare the document with status field
            moneyline_doc = {
                'game_id': game_id,
                'sport': SPORTS[sport_key],
                'league': get_league_name(sport_key),
                'event_date': commence_time,
                'teams': {
                    'home': {
                        'name': home_team,
                        'moneyline': home_moneyline
                    },
                    'away': {
                        'name': away_team,
                        'moneyline': away_moneyline
                    }
                },
                'status': 'Scheduled' if commence_time > current_time else 'In Progress',
                'result': {
                    'home_score': None,  # To be updated after the game
                    'away_score': None,  # To be updated after the game
                    'winner': None        # Can be null if game hasn't been played yet
                },
                'last_updated': current_time
            }

            # Create an upsert operation
            operations.append(
                pymongo.UpdateOne(
                    {'game_id': game_id},
                    {'$set': moneyline_doc},
                    upsert=True
                )
            )

            logger.info(f"Processed game: {home_team} vs {away_team} on {commence_time}")

        except Exception as e:
            logger.error(f"Error processing event {event.get('id', 'Unknown')}: {e}")
            continue

    # Execute bulk operations if any
    if operations:
        try:
            result = moneylines_collection.bulk_write(operations)
            logger.info(f"Processed {len(operations)} games for {SPORTS[sport_key]}")
            logger.info(f"Updated: {result.modified_count}, Inserted: {result.upserted_count}")
        except Exception as e:
            logger.error(f"Bulk write error: {e}")

def get_league_name(sport_key):
    """
    Returns the league name based on the sport key.
    """
    return SPORTS.get(sport_key, 'Unknown')

# --------------------- Main Execution Flow ---------------------
def main():
    # Get all configured sports, including MLB
    sports_to_fetch = list(SPORTS.keys())  # Now includes 'baseball_mlb'

    for sport_key in sports_to_fetch:
        logger.info(f"Fetching odds for {SPORTS[sport_key]}")
        odds_data = fetch_moneyline_odds(sport_key)
        if odds_data:
            process_and_store_odds(odds_data, sport_key)
        else:
            logger.warning(f"No odds data fetched for sport: {SPORTS[sport_key]}")

    client.close()
    logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    main()
