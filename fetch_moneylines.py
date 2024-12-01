import json
import logging
from datetime import datetime, timezone

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

    :param sport_key: Sport identifier as per The Odds API (e.g., 'basketball_nba')
    :return: List of events with odds data
    """
    url = f"{API_BASE_URL}{sport_key}/odds"
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': REGION,          # e.g., 'us'
        'markets': MARKET,          # e.g., 'h2h' for moneyline
        'oddsFormat': ODDS_FORMAT,  # 'american' or 'decimal'
        'dateFormat': DATE_FORMAT   # 'iso' or 'unix'
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        odds_data = response.json()
        logger.info(f"Fetched odds data for sport: {SPORTS.get(sport_key, 'Unknown Sport')}")
        return odds_data
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err} - Status Code: {response.status_code}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request exception occurred: {req_err}")
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON decode error: {json_err}")
    return []

# --------------------- Processing and Storing Data ---------------------
def process_and_store_odds(odds_data, sport_key):
    """
    Processes odds data and stores it in MongoDB.

    :param odds_data: List of events with odds data
    :param sport_key: Sport identifier
    """
    operations = []

    for event in odds_data:
        try:
            game_id = event.get('id')
            commence_time_str = event.get('commence_time')  # ISO 8601 format
            commence_time = datetime.strptime(commence_time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            home_team = event.get('home_team')
            away_team = event.get('away_team')
            bookmakers = event.get('bookmakers', [])

            if not all([game_id, commence_time, home_team, away_team, bookmakers]):
                logger.warning(f"Incomplete data for event ID {game_id}. Skipping.")
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

            # Prepare the document
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
                'result': {
                    'home_score': None,  # To be updated after the game
                    'away_score': None,  # To be updated after the game
                    'winner': None        # Can be null if game hasn't been played yet
                },
                'last_updated': datetime.now(timezone.utc)
            }

            # Define the unique filter to upsert
            filter_doc = {
                'game_id': game_id
            }

            # Create an upsert operation
            operations.append(
                pymongo.UpdateOne(filter_doc, {'$set': moneyline_doc}, upsert=True)
            )

        except Exception as e:
            logger.error(f"Error processing event ID {event.get('id', 'Unknown')}: {e}")
            continue

    if operations:
        try:
            result = moneylines_collection.bulk_write(operations)
            logger.info(f"Inserted/Updated {result.upserted_count + result.modified_count} documents.")
        except pymongo.errors.BulkWriteError as bwe:
            logger.error(f"Bulk write error: {bwe.details}")
        except Exception as e:
            logger.error(f"Unexpected error during MongoDB operations: {e}")
    else:
        logger.info("No moneyline data to update.")

def get_league_name(sport_key):
    """
    Returns the league name based on the sport key.
    """
    league_mapping = {
        'basketball_nba': 'NBA',
        'americanfootball_nfl': 'NFL',
        'basketball_ncaab': 'NCAAB',
        'americanfootball_ncaaf': 'College Football',
        'icehockey_nhl': 'NHL'
    }
    return league_mapping.get(sport_key, 'Unknown')

# --------------------- Main Execution Flow ---------------------
def main():
    sports_to_fetch = [
        'basketball_nba',
        'americanfootball_nfl',
        'basketball_ncaab',
        'americanfootball_ncaaf',
        'icehockey_nhl'
    ]

    for sport_key in sports_to_fetch:
        odds_data = fetch_moneyline_odds(sport_key)
        if odds_data:
            process_and_store_odds(odds_data, sport_key)
        else:
            logger.warning(f"No odds data fetched for sport: {SPORTS[sport_key]}")

    client.close()
    logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    main()
