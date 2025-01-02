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
    DATE_FORMAT
)

# --------------------- Logging Configuration ---------------------
logger = logging.getLogger('UpdateGameStatus')
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

# --------------------- Updating Game Status ---------------------
def fetch_scores(sport='basketball_nba'):
    """
    Fetches scores for specified sport from The Odds API.
    :param sport: Sport key (basketball_nba, americanfootball_nfl, basketball_ncaab, americanfootball_ncaaf, icehockey_nhl)
    :return: List of games with scores and statuses.
    """
    url = f"{API_BASE_URL}{sport}/scores/"
    params = {
        'apiKey': ODDS_API_KEY,
        'daysFrom': 3,
        'dateFormat': DATE_FORMAT
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        scores_data = response.json()
        logger.info(f"Fetched {sport} scores data successfully.")
        return scores_data
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request exception occurred while fetching {sport} scores: {req_err}")
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON decode error for {sport}: {json_err}")

    return []

def update_game_status():
    """
    Updates results for all configured sports games.
    """
    try:
        games_to_update = moneylines_collection.find({
            'result.winner': None
        })

        if moneylines_collection.count_documents({'result.winner': None}) == 0:
            logger.info("No games with null results to update.")
            return

        # Fetch scores for all sports including MLB
        all_scores = []
        for sport_key in SPORTS.keys():
            logger.info(f"Fetching scores for {SPORTS[sport_key]}")
            scores = fetch_scores(sport_key)
            if scores:
                all_scores.extend(scores)
            else:
                logger.warning(f"No scores fetched for {SPORTS[sport_key]}")

        if not all_scores:
            logger.warning("No scores data fetched for any sport.")
            return

        operations = []

        for game in games_to_update:
            game_id = game.get('game_id')

            if not game_id:
                logger.warning("Game without a game_id found. Skipping.")
                continue

            # Find corresponding score data
            score_data = next((item for item in all_scores if item['id'] == game_id), None)

            if not score_data:
                continue

            if score_data.get('completed', False):
                scores = score_data.get('scores', [])
                home_score = next((score['score'] for score in scores if score['name'] == game['teams']['home']['name']), None)
                away_score = next((score['score'] for score in scores if score['name'] == game['teams']['away']['name']), None)

                if home_score is not None and away_score is not None:
                    winner = game['teams']['home']['name'] if int(home_score) > int(away_score) else game['teams']['away']['name']

                    update_doc = {
                        '$set': {
                            'result.home_score': int(home_score),
                            'result.away_score': int(away_score),
                            'result.winner': winner,
                            'status': 'Completed',
                            'last_updated': datetime.now(timezone.utc)
                        }
                    }

                    operations.append(
                        pymongo.UpdateOne({'game_id': game_id}, update_doc)
                    )

        if operations:
            try:
                result = moneylines_collection.bulk_write(operations)
                logger.info(f"Updated {result.modified_count} games to 'Completed' status.")
            except pymongo.errors.BulkWriteError as bwe:
                logger.error(f"Bulk write error: {bwe.details}")
            except Exception as e:
                logger.error(f"Unexpected error during MongoDB operations: {e}")
        else:
            logger.info("No games were updated.")

    except Exception as e:
        logger.error(f"Error updating game statuses: {e}")

# --------------------- Main Execution Flow ---------------------
def main():
    update_game_status()

    # Close MongoDB connection
    client.close()
    logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    main()
