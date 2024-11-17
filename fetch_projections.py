import requests
from datetime import datetime
from app import mongo

# API endpoint
url = 'https://api.prizepicks.com/projections'

# Parameters to filter for NBA
params = {
    'league_id': '7',  # Replace with the correct NBA league ID
    'per_page': 1000,
}

# Fetch the projections
response = requests.get(url, params=params)
if response.status_code == 200:
    projections_data = response.json()
else:
    print(f'Error fetching data: {response.status_code}')
    exit()

# Access the list of projections
projections = projections_data.get('data', [])

for projection in projections:
    attributes = projection['attributes']
    player_name = attributes['name']
    stat_type = attributes['stat_type']
    projected_value = attributes['line_score']
    game_time = attributes['starts_at']
    
    # Prepare the document
    proj_doc = {
        'player_name': player_name,
        'stat_type': stat_type,
        'projected_value': projected_value,
        'game_time': datetime.strptime(game_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    }
    
    # Insert into MongoDB
    mongo.db.projections.update_one(
        {'player_name': player_name, 'stat_type': stat_type, 'game_time': proj_doc['game_time']},
        {'$set': proj_doc},
        upsert=True
    )
