import requests
from datetime import datetime
from app import mongo
from pymongo import UpdateOne
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API endpoint (replace with your actual endpoint)
url = 'https://api.prizepicks.com/projections'

# Parameters to filter for NBA (adjust as needed)
params = {
    'league_id': '7',  # Example league ID for NBA
    'per_page': 1000,
}

# Fetch the projections
response = requests.get(url, params=params)
if response.status_code == 200:
    projections_data = response.json()
    logger.info("Fetched projections data successfully.")
else:
    logger.error(f'Error fetching data: {response.status_code}')
    exit(1)

# Access the list of projections
projections = projections_data.get('data', [])

operations = []

for projection in projections:
    attributes = projection['attributes']
    player_name = attributes.get('name', 'Unknown')
    player_stat = attributes.get('stat_type', 'Unknown')
    projected_value = attributes.get('line_score', 0)
    game_time_str = attributes.get('starts_at', None)
    
    if game_time_str:
        game_time = datetime.strptime(game_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
    else:
        game_time = None

    # Prepare the document
    proj_doc = {
        'player_name': player_name,
        'player_stat': player_stat,
        'projected_value': projected_value,
        'actual_value': None,  # To be updated later
        'result': None,        # To be determined later
        'game_time': game_time
    }

    # Define the unique filter to upsert
    filter_doc = {
        'player_name': player_name,
        'player_stat': player_stat,
        'game_time': game_time
    }

    # Create an upsert operation
    operations.append(
        UpdateOne(filter_doc, {'$set': proj_doc}, upsert=True)
    )

if operations:
    try:
        result = mongo.db.projections.bulk_write(operations)
        logger.info(f"Inserted/Updated {result.upserted_count + result.modified_count} documents.")
    except Exception as e:
        logger.error(f"Error writing to MongoDB: {e}")
else:
    logger.info("No projections to update.")
