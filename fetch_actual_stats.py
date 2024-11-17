import requests
from datetime import datetime, timedelta
from app import mongo
from pymongo import UpdateOne
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Calculate today's date in UTC (adjust if necessary)
today = datetime.utcnow().date()

# API endpoint for actual stats (replace with the actual endpoint)
# Example using balldontlie API for NBA stats
stats_url = 'https://www.balldontlie.io/api/v1/stats'

# Parameters to filter for today's date
params = {
    'dates[]': today.isoformat(),
    'per_page': 100,  # Adjust as needed
}

# Fetch the actual stats
response = requests.get(stats_url, params=params)
if response.status_code == 200:
    actual_stats_data = response.json()
    logger.info("Fetched actual stats data successfully.")
else:
    logger.error(f'Error fetching actual stats: {response.status_code}')
    exit(1)

actual_stats = actual_stats_data.get('data', [])

operations = []

for stat in actual_stats:
    player = stat.get('player', {})
    player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
    stat_types = {
        'Points': stat.get('pts', 0),
        'Rebounds': stat.get('reb', 0),
        'Assists': stat.get('ast', 0),
        # Add other stat types as needed
    }

    for stat_type, actual_value in stat_types.items():
        if player_name and stat_type:
            # Define the filter to find the corresponding projection
            filter_doc = {
                'player_name': player_name,
                'player_stat': stat_type,
                'game_time': {
                    '$lte': datetime.combine(today, datetime.max.time()),
                    '$gte': datetime.combine(today, datetime.min.time())
                }
            }

            # Define the update
            update_doc = {
                '$set': {
                    'actual_value': actual_value
                }
            }

            # Optionally, determine the result here or handle it in the Flask app
            operations.append(
                UpdateOne(filter_doc, update_doc, upsert=False)
            )

if operations:
    try:
        result = mongo.db.projections.bulk_write(operations)
        logger.info(f"Updated {result.modified_count} documents with actual stats.")
    except Exception as e:
        logger.error(f"Error updating MongoDB: {e}")
else:
    logger.info("No actual stats to update.")
