import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import logging
import json  # Add this import
from mongo_query_generator import MongoQueryGenerator
import os
import google.generativeai as genai
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Add this line for session management

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(username):
    return User.get(username)

# --------------------- Logging Configuration ---------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
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

query_generator = MongoQueryGenerator(os.getenv('GEMINI_KEY'))

# --------------------- Helper Functions ---------------------
def fetch_games(target_date, timezone="UTC", page=1, per_page=10):
    try:
        user_timezone = pytz.timezone(timezone)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        query = {"event_date": {"$gte": start_of_day, "$lt": end_of_day}}
        
        total_games = moneylines_collection.count_documents(query)
        if total_games == 0:
            return [], 0

        skip = (page - 1) * per_page
        games_cursor = moneylines_collection.find(query).skip(skip).limit(per_page)

        games = []
        for game in games_cursor:
            event_date_utc = game.get('event_date')
            if isinstance(event_date_utc, str):
                event_date_utc = datetime.fromisoformat(event_date_utc)
            event_date_local = event_date_utc.astimezone(user_timezone)

            games.append({
                'event_date': event_date_local,
                'home_team': game.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                'home_moneyline': game.get('teams', {}).get('home', {}).get('moneyline', 'N/A'),
                'away_team': game.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                'away_moneyline': game.get('teams', {}).get('away', {}).get('moneyline', 'N/A'),
                'winner': game.get('result', {}).get('winner', 'N/A'),
                'status': game.get('status', 'In Progress')
            })

        games = sorted(games, key=lambda x: x['event_date'])
        return games, total_games
    except Exception as e:
        logger.error(f"Error in fetch_games function: {e}")
        return [], 0

def fetch_team_games(team, page=1, per_page=20):
    """
    Fetch games for a specific team from the database.
    
    :param team: Team name to filter games by
    :param page: Current page number for pagination
    :param per_page: Number of games per page
    :return: List of games and total count of matching games
    """
    try:
        query = {
            '$or': [
                {'teams.home.name': team},
                {'teams.away.name': team}
            ]
        }

        # Pagination setup
        total_games = moneylines_collection.count_documents(query)
        if total_games == 0:
            return [], 0

        skip = (page - 1) * per_page
        games_cursor = moneylines_collection.find(query).skip(skip).limit(per_page)

        # Process games
        games = []
        for game in games_cursor:
            games.append({
                'event_date': game.get('event_date'),
                'home_team': game.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                'home_moneyline': game.get('teams', {}).get('home', {}).get('moneyline', 'N/A'),
                'away_team': game.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                'away_moneyline': game.get('teams', {}).get('away', {}).get('moneyline', 'N/A'),
                'winner': game.get('result', {}).get('winner', 'N/A'),
                'status': game.get('status', 'In Progress'),
            })

        games = sorted(games, key=lambda x: x['event_date'])
        return games, total_games
    except Exception as e:
        logger.error(f"Error in fetch_team_games function: {e}")
        return [], 0

def get_unique_teams():
    """
    Retrieves a sorted list of unique team names from the database.
    :return: List of team names.
    """
    try:
        home_teams = moneylines_collection.distinct('teams.home.name')
        away_teams = moneylines_collection.distinct('teams.away.name')
        unique_teams = sorted(set(home_teams + away_teams))
        logger.info(f"Unique teams retrieved: {unique_teams}")
        return unique_teams
    except Exception as e:
        logger.error(f"Error fetching unique teams: {e}")
        return []

# --------------------- Routes ---------------------
@app.route('/')
@login_required
def index():
    try:
        now_utc = datetime.now(pytz.utc)
        timezone = request.args.get('timezone', 'UTC')
        page = int(request.args.get('page', 1))
        games_today, total_games = fetch_games(target_date=now_utc, timezone=timezone, page=page, per_page=10)
        total_pages = (total_games + 10 - 1) // 10

        return render_template('index.html', games=games_today, page_title="Today's Games",
                               current_page=page, total_pages=total_pages, timezone=timezone)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template('error.html', message="An error occurred while fetching today's games.")

@app.route('/next_day')
@login_required
def next_day():
    try:
        next_day_date = datetime.now(pytz.utc) + timedelta(days=1)
        timezone = request.args.get('timezone', 'UTC')
        page = int(request.args.get('page', 1))
        games_next_day, total_games = fetch_games(target_date=next_day_date, timezone=timezone, page=page, per_page=10)
        total_pages = (total_games + 10 - 1) // 10

        return render_template('next_day.html', games=games_next_day, page_title="Upcoming Games",
                               current_page=page, total_pages=total_pages, timezone=timezone)
    except Exception as e:
        logger.error(f"Error in next_day route: {e}")
        return render_template('error.html', message="An error occurred while fetching upcoming games.")

@app.route('/previous_games')
@login_required
def previous_games():
    try:
        previous_day_date = datetime.now(pytz.utc) - timedelta(days=1)
        timezone = request.args.get('timezone', 'UTC')
        page = int(request.args.get('page', 1))
        games_previous_day, total_games = fetch_games(target_date=previous_day_date, timezone=timezone, page=page, per_page=10)
        total_pages = (total_games + 10 - 1) // 10

        return render_template('previous_games.html', games=games_previous_day, page_title="Past Games",
                               current_page=page, total_pages=total_pages, timezone=timezone)
    except Exception as e:
        logger.error(f"Error in previous_games route: {e}")
        return render_template('error.html', message="An error occurred while fetching past games.")

@app.route('/team_stats', methods=['GET', 'POST'])
@login_required
def team_stats():
    try:
        if request.method == 'POST':
            team = request.form.get('team')
            if not team:
                return render_template('team_stats.html', error="Please select a team.", teams=get_unique_teams())
            return redirect(url_for('team_stats', team=team, page=1))

        team = request.args.get('team')
        page = int(request.args.get('page', 1))
        per_page = 10
        games, total_games = fetch_team_games(team, page=page, per_page=per_page) if team else ([], 0)

        # Calculate win statistics
        total_games_played = len(games)
        underdog_wins = 0
        favored_wins = 0
        total_underdog_games = 0
        total_favored_games = 0

        for game in games:
            if game['home_team'] == team:
                is_favored = game['home_moneyline'] < game['away_moneyline']
                did_win = game['winner'] == team
            else:
                is_favored = game['away_moneyline'] < game['home_moneyline']
                did_win = game['winner'] == team

            if is_favored:
                total_favored_games += 1
                if did_win:
                    favored_wins += 1
            else:
                total_underdog_games += 1
                if did_win:
                    underdog_wins += 1

        # Calculate percentages
        underdog_win_rate = (underdog_wins / total_underdog_games) * 100 if total_underdog_games > 0 else 0
        favored_win_rate = (favored_wins / total_favored_games) * 100 if total_favored_games > 0 else 0

        total_pages = (total_games + per_page - 1) // per_page

        return render_template(
            'team_stats.html',
            games=games,
            selected_team=team,
            teams=get_unique_teams(),
            page_title=f"Stats for {team}" if team else "Team Statistics",
            current_page=page,
            total_pages=total_pages,
            underdog_win_rate=underdog_win_rate,
            favored_win_rate=favored_win_rate,
            total_underdog_games=total_underdog_games,
            total_favored_games=total_favored_games,
        )
    except Exception as e:
        logger.error(f"Error in team_stats route: {e}")
        return render_template('error.html', message="An error occurred while fetching team stats.")

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    try:
        if request.method == 'POST':
            natural_query = request.form.get('query')
            if not natural_query:
                return render_template('search.html', error="Please enter a query")

            # Generate MongoDB query from natural language
            mongo_query = query_generator.generate_query(natural_query)
            mongo_query = query_generator.process_date_filters(mongo_query)

            # Execute the query
            results = list(moneylines_collection.find(mongo_query).limit(20))

            return render_template('search.html', 
                                results=results, 
                                query=natural_query, 
                                mongo_query=json.dumps(mongo_query, indent=2))

        return render_template('search.html')
    except Exception as e:
        logger.error(f"Error in search route: {e}")
        return render_template('error.html', message="An error occurred during search.")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.get(username)
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        return render_template('login.html', error="Invalid username or password")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.get(username):
            return render_template('register.html', error="Username already exists")
        
        user = User(username=username, email=email)
        user.set_password(password)
        user.save()
        
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

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
