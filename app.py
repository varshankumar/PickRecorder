import os
from flask import Flask, render_template, request, url_for
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import logging

app = Flask(__name__)

# --------------------- Logging Configuration ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------- MongoDB Configuration ---------------------
# Retrieve MongoDB URI from environment variables
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    logger.error("MONGO_URI not found in environment variables.")
    raise EnvironmentError("MONGO_URI not found in environment variables.")

# Initialize MongoDB client
try:
    client = MongoClient(MONGO_URI)
    db = client.sports_odds  # Replace with your actual database name
    moneylines_collection = db.moneylines  # Replace with your actual collection name
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise e

# --------------------- Helper Function ---------------------
def fetch_games(target_date):
    """
    Fetches games for a given date from MongoDB.
    :param target_date: datetime object representing the target date in UTC.
    :return: List of game dictionaries.
    """
    try:
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        logger.info(f"Fetching games from {start_of_day} to {end_of_day} UTC.")

        # Query for games happening on target_date
        games_today_cursor = moneylines_collection.find({
            'event_date': {
                '$gte': start_of_day,
                '$lt': end_of_day
            }
        })

        games_today = list(games_today_cursor)
        total_fetched = len(games_today)
        logger.info(f"Total games fetched from DB: {total_fetched}")

        if total_fetched == 0:
            logger.warning("No games found for the specified date in the database.")
            return []

        games = []
        processed_count = 0  # Counter for debugging

        for game in games_today:
            processed_count += 1
            home_team = game['teams']['home']['name']
            home_moneyline = game['teams']['home']['moneyline']
            away_team = game['teams']['away']['name']
            away_moneyline = game['teams']['away']['moneyline']
            winner = game['result'].get('winner')  # Use .get() to handle cases where 'winner' might not exist

            logger.info(f"Processing game {processed_count}: {home_team} vs {away_team} at {game['event_date']}")

            # Convert event_date to local timezone
            event_date_local = game['event_date'].astimezone(pytz.timezone('UTC'))  # Modify timezone if needed

            # Determine game status
            if winner:
                status = 'Completed'
            else:
                status = 'Upcoming'

            games.append({
                'sport': game['sport'],
                'league': game['league'],
                'event_date': event_date_local,
                'home_team': home_team,
                'home_moneyline': home_moneyline,
                'away_team': away_team,
                'away_moneyline': away_moneyline,
                'winner': winner if winner else 'N/A',
                'status': status
            })

        logger.info(f"Total games to display: {len(games)}")
        # Sort the list by event_date ascending (earliest first)
        games = sorted(games, key=lambda x: x['event_date'])

        return games
    except Exception as e:
        logger.error(f"Error fetching games: {e}")
        return []

# --------------------- Flask Routes ---------------------
@app.route('/')
def index():
    """
    Fetches today's games from MongoDB and renders them to the index.html template.
    """
    try:
        # Define the timezone (modify as needed)
        local_tz = pytz.timezone('UTC')  # Change 'UTC' to your desired timezone, e.g., 'America/New_York'

        # Get current date in UTC
        now_utc = datetime.now(pytz.utc)
        games_today = fetch_games(now_utc)

        return render_template('index.html', games=games_today, page_title="Today's Games")
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template('error.html', message="An error occurred while fetching today's games.")

@app.route('/next_day')
def next_day():
    """
    Fetches next day's games from MongoDB and renders them to the next_day.html template.
    """
    try:
        # Define the timezone (modify as needed)
        local_tz = pytz.timezone('UTC')  # Change 'UTC' to your desired timezone, e.g., 'America/New_York'

        # Calculate next day's date in UTC
        now_utc = datetime.now(pytz.utc)
        next_day_date = now_utc + timedelta(days=1)
        games_next_day = fetch_games(next_day_date)

        return render_template('next_day.html', games=games_next_day, page_title="Next Day's Games")
    except Exception as e:
        logger.error(f"Error in next_day route: {e}")
        return render_template('error.html', message="An error occurred while fetching next day's games.")

# --------------------- Run the Flask App ---------------------
if __name__ == '__main__':
    try:
        # Retrieve the port number from environment variables (set by Render)
        port = int(os.environ.get('PORT', 5000))
        # Run the Flask app on all available IPs (0.0.0.0) and the specified port
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Failed to run the Flask app: {e}")
