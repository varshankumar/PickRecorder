from flask import Flask, render_template
from pymongo import MongoClient
from config import MONGO_URI

app = Flask(__name__)

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client.sports_odds
moneylines_collection = db.moneylines

@app.route('/')
def index():
    # Fetch all games where underdogs won
    # Assuming underdogs have positive moneyline odds
    # and favorites have negative moneyline odds
    # We'll define a game as an underdog win if the away or home team was not favored and won
    
    games = moneylines_collection.find()
    
    underdog_wins = []
    
    for game in games:
        home_team = game['teams']['home']['name']
        home_moneyline = game['teams']['home']['moneyline']
        away_team = game['teams']['away']['name']
        away_moneyline = game['teams']['away']['moneyline']
        winner = game['result']['winner']
        
        # Determine if home team was underdog
        home_underdog = home_moneyline > 0
        # Determine if away team was underdog
        away_underdog = away_moneyline > 0
        
        # Check if an underdog won
        if (home_underdog and winner == home_team) or (away_underdog and winner == away_team):
            underdog_wins.append({
                'sport': game['sport'],
                'league': game['league'],
                'event_date': game['event_date'],
                'home_team': home_team,
                'home_moneyline': home_moneyline,
                'away_team': away_team,
                'away_moneyline': away_moneyline,
                'winner': winner
            })
    
    return render_template('index.html', underdog_wins=underdog_wins)

if __name__ == '__main__':
    app.run(debug=True)
