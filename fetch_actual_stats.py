import requests
from app import mongo

# Example using balldontlie API for NBA stats
date = '2023-10-17'  # Replace with the desired date

stats_url = f'https://www.balldontlie.io/api/v1/stats?dates[]={date}&per_page=100'

response = requests.get(stats_url)
if response.status_code == 200:
    actual_stats_data = response.json()
else:
    print(f'Error fetching data: {response.status_code}')
    exit()

actual_stats = actual_stats_data.get('data', [])

for stat in actual_stats:
    player_name = f"{stat['player']['first_name']} {stat['player']['last_name']}"
    # Example stat types
    stat_types = {
        'Points': stat['pts'],
        'Rebounds': stat['reb'],
        'Assists': stat['ast'],
        # Add other stat types as needed
    }
    
    for stat_type, actual_value in stat_types.items():
        # Update the projection with the actual value
        mongo.db.projections.update_one(
            {'player_name': player_name, 'stat_type': stat_type},
            {'$set': {'actual_value': actual_value}},
            upsert=False
        )
