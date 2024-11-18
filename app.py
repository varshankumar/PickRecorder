import os
from flask import Flask, render_template, request, jsonify, abort, url_for, redirect
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import logging

app = Flask(__name__)

# --------------------- Logging Configuration ---------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --------------------- MongoDB Configuration ---------------------
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    logger.error("MONGO_URI not found in environment variables.")
    raise EnvironmentError("MONGO_URI not found in environment variables.")

try:
    client = MongoClient(MONGO_URI)
    db = client.sports_odds
    moneylines_collection = db.moneylines
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise e

# --------------------- Helper Functions ---------------------
def fetch_games(target_date, status=None, team=None, page=1, per_page=10):
    try:
        query = {}
        logger.info("Starting fetch_games function.")

        # Apply filters
        if team:
            query['$or'] = [
                {'teams.home.name': team},
                {'teams.away.name': team}
            ]
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        query['event_date'] = {'$gte': start_of_day, '$lt': end_of_day}
        if status:
            query['status'] = status

        total_games = moneylines_collection.count_documents(query)
        if total_games == 0:
            return [], 0

        skip = (page - 1) * per_page
        games_cursor = moneylines_collection.find(query).skip(skip).limit(per_page)

        games = []
        for game in games_cursor:
            games.append({
                'event_date': game.get('event_date'),
                'home_team': game.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                'home_moneyline': game.get('teams', {}).get('home', {}).get('moneyline', 'N/A'),
                'away_team': game.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                'away_moneyline': game.get('teams', {}).get('away', {}).get('moneyline', 'N/A'),
                'winner': game.get('result', {}).get('winner', 'N/A'),
                'status': game.get('status', 'In Progress')
            })

        games = sorted(games, key=lambda x: x['event_date'])
        logger.info(f"Processed games: {games}")
        return games, total_games
    except Exception as e:
        logger.error(f"Error in fetch_games function: {e}")
        return [], 0




# --------------------- Routes ---------------------
@app.route('/')
def index():
    try:
        now_utc = datetime.now(pytz.utc)
        page = int(request.args.get('page', 1))
        per_page = 10
        games_today, total_games = fetch_games(target_date=now_utc, page=page, per_page=per_page)
        total_pages = (total_games + per_page - 1) // per_page

        return render_template('index.html', games=games_today, page_title="Today's Games",
                               current_page=page, total_pages=total_pages)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template('error.html', message="An error occurred while fetching today's games.")

@app.route('/next_day')
def next_day():
    try:
        next_day_date = datetime.now(pytz.utc) + timedelta(days=1)
        page = int(request.args.get('page', 1))
        per_page = 10
        games_next_day, total_games = fetch_games(target_date=next_day_date, page=page, per_page=per_page)
        total_pages = (total_games + per_page - 1) // per_page

        return render_template('next_day.html', games=games_next_day, page_title="Next Day's Games",
                               current_page=page, total_pages=total_pages)
    except Exception as e:
        logger.error(f"Error in next_day route: {e}")
        return render_template('error.html', message="An error occurred while fetching next day's games.")

@app.route('/previous_games')
def previous_games():
    try:
        previous_day_date = datetime.now(pytz.utc) - timedelta(days=1)
        page = int(request.args.get('page', 1))
        per_page = 10
        games_previous_day, total_games = fetch_games(target_date=previous_day_date, page=page, per_page=per_page)
        total_pages = (total_games + per_page - 1) // per_page

        return render_template('previous_games.html', games=games_previous_day, page_title="Previous Day's Games",
                               current_page=page, total_pages=total_pages)
    except Exception as e:
        logger.error(f"Error in previous_games route: {e}")
        return render_template('error.html', message="An error occurred while fetching previous day's games.")

@app.route('/team_stats', methods=['GET', 'POST'])
def team_stats():
    if request.method == 'POST':
        team = request.form.get('team')
        if not team:
            return render_template('team_stats.html', error="Please select a team.", teams=get_unique_teams())
        return redirect(url_for('team_stats', team=team, page=1))

    team = request.args.get('team')
    page = int(request.args.get('page', 1))
    per_page = 10
    if team:
        games, total_games = fetch_games(datetime.now(pytz.utc), team=team, page=page, per_page=per_page)
        total_pages = (total_games + per_page - 1) // per_page

        return render_template('team_stats.html', games=games, selected_team=team,
                               teams=get_unique_teams(), page_title=f"Stats for {team}",
                               current_page=page, total_pages=total_pages)

    return render_template('team_stats.html', teams=get_unique_teams(), page_title="Team Statistics")

# --------------------- Error Handling ---------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', message="Page not found."), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html', message="Internal server error."), 500

# --------------------- Run the App ---------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
