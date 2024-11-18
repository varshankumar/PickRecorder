# update_game_results.py

import os
import requests
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import logging

# --------------------- Configuration ---------------------

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
MONGO_URI = os.getenv('MONGO_URI')
ODDS_API_KEY = os.getenv('ODDS_API_KEY')

if not MONGO_URI or not ODDS_API_KEY:
    raise EnvironmentError("MONGO_URI and ODDS_API_KEY must be set in the environment variables.")

# Odds API Configuration
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/scores"

# Define the sports and corresponding leagues
SPORTS = {
    "basketball_nba": "NBA",
    "american_football_nfl": "NFL"
}

# Define the region and market (you can adjust these as needed)
REGION = "us"  # Available regions: us, uk, eu, au
MARKET = "h2h"  # Head-to-head market

# Timezone configuration
UTC = pytz.utc

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("update_game_results.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# --------------------- MongoDB Connection ---------------------

try:
    client = MongoClient(MONGO_URI)
    db = client.sports_odds  # Database name
    collection = db.moneylines  # Collection name
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise e

# --------------------- Helper Functions ---------------------

def fetch_games(sport_key):
    """
    Fetches today's games for a given sport from the Odds API.
    :param sport_key: The sport key as per the Odds API (e.g., 'basketball_nba')
    :return: List of game dictionaries
    """
    url = ODDS_API_URL.format(sport=sport_key)
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': REGION,
        'markets': MARKET,
        'oddsFormat': 'american',
        'dateFormat': 'iso'  # ISO date format
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        games = response.json()
        logger.info(f"Fetched {len(games)} games for sport: {sport_key}")
        return games
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred while fetching {sport_key}: {http_err}")
    except Exception as err:
        logger.error(f"Error occurred while fetching {sport_key}: {err}")
    return []

def determine_winner(game):
    """
    Determines the winner of a game based on scores.
    :param game: Game dictionary from the Odds API
    :return: Name of the winning team or None if the game is not completed
    """
    if game.get('status') != 'closed':
        return None  # Game is not completed

    home_score = game.get('home_score')
    away_score = game.get('away_score')

    if home_score is None or away_score is None:
        return None  # Incomplete score data

    if home_score > away_score:
        return game['home_team']
    elif away_score > home_score:
        return game['away_team']
    else:
        return "Draw"  # In rare cases of a draw

def update_game_result(game, winner, league):
    """
    Updates the game document in MongoDB with the winner.
    :param game: Game dictionary from the Odds API
    :param winner: Name of the winning team
    :param league: League name (e.g., 'NBA', 'NFL')
    """
    # Extract necessary details to identify the document
    event_date_str = game.get('commence_time')  # ISO format string
    event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00')).replace(tzinfo=UTC)

    home_team = game.get('home_team')
    away_team = game.get('away_team')

    # Construct the query to find the corresponding game document
    query = {
        'sport': SPORTS[sport_key],
        'league': league,
        'event_date': event_date,
        'teams.home.name': home_team,
        'teams.away.name': away_team
    }

    # Update the 'result.winner' field
    update = {
        '$set': {
            'result.winner': winner
        }
    }

    try:
        result = collection.update_one(query, update)
        if result.matched_count:
            logger.info(f"Updated winner for game: {home_team} vs {away_team} - Winner: {winner}")
        else:
            logger.warning(f"No matching game found in DB for: {home_team} vs {away_team} on {event_date}")
    except Exception as e:
        logger.error(f"Failed to update game result for {home_team} vs {away_team}: {e}")

# --------------------- Main Execution ---------------------

if __name__ == "__main__":
    # Iterate over each sport and fetch games
    for sport_key, league in SPORTS.items():
        games = fetch_games(sport_key)

        for game in games:
            winner = determine_winner(game)

            if winner:
                update_game_result(game, winner, league)
            else:
                logger.info(f"Game not completed or winner not determined: {game['home_team']} vs {game['away_team']}")

    logger.info("Game results update script completed.")
