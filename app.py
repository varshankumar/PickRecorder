from flask import Flask, render_template
from flask_pymongo import PyMongo
from dotenv import load_dotenv
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Get the MongoDB connection string
mongo_uri = os.getenv("MONGO_URI")
logger.info(f"MONGO_URI: {mongo_uri}")

# Check if MONGO_URI is loaded
if not mongo_uri:
    logger.error("Error: MONGO_URI environment variable not set.")
    exit(1)

# Set up the MongoDB connection string
app.config["MONGO_URI"] = mongo_uri

# Initialize PyMongo
try:
    mongo = PyMongo(app)
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    mongo = None

@app.route('/')
def index():
    if not mongo:
        return "Error: Unable to connect to the database.", 500

    try:
        # Fetch data from the 'projections' collection
        projections = mongo.db.projections.find()
    except Exception as e:
        logger.error(f"Error fetching data from MongoDB: {e}")
        return "Error fetching data from the database.", 500

    # Prepare data for rendering
    display_results = []
    for proj in projections:
        projected_value = proj.get('projected_value', 0)
        actual_value = proj.get('actual_value', 0)
        player_name = proj.get('player_name', 'Unknown')
        player_stat = proj.get('player_stat', 'Unknown')
        game_time = proj.get('game_time', None)

        # Determine over/under/equal result
        if actual_value > projected_value:
            result = 'Over'
        elif actual_value < projected_value:
            result = 'Under'
        else:
            result = 'Equal'

        display_results.append({
            'player_name': player_name,
            'player_stat': player_stat,
            'projected_value': projected_value,
            'actual_value': actual_value,
            'result': result,
            'game_time': game_time
        })

    return render_template('results.html', results=display_results)

if __name__ == '__main__':
    app.run(debug=True)
