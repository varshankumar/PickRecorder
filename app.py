from flask import Flask, render_template
from flask_pymongo import PyMongo
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Set up the MongoDB connection string
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")

# Initialize PyMongo
mongo = PyMongo(app)

@app.route('/')
def index():
    # Fetch data from the 'projections' collection
    projections = mongo.db.projections.find()
    
    # Prepare data for rendering
    display_results = []
    for proj in projections:
        projected_value = proj.get('projected_value', 0)
        actual_value = proj.get('actual_value', 0)
        player_name = proj.get('player_name', 'Unknown')
        stat_type = proj.get('stat_type', 'Unknown')
        
        # Determine over/under result
        if actual_value > projected_value:
            result = 'Over'
        elif actual_value < projected_value:
            result = 'Under'
        else:
            result = 'Push'
        
        display_results.append({
            'player_name': player_name,
            'stat_type': stat_type,
            'projected_value': projected_value,
            'actual_value': actual_value,
            'result': result
        })
    
    return render_template('results.html', results=display_results)

if __name__ == '__main__':
    app.run()
