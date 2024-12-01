import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
app.secret_key = os.getenv('SECRET_KEY')

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
def fetch_games(target_date, timezone=None, page=1, per_page=10, sports=None):
    try:
        timezone = timezone or session.get('timezone', 'UTC')
        user_timezone = pytz.timezone(timezone)
        
        # Make sure target_date is timezone aware in user's timezone
        if target_date.tzinfo is None:
            target_date = user_timezone.localize(target_date)
        else:
            target_date = target_date.astimezone(user_timezone)
        
        # Get start and end of day in user's timezone
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convert to UTC for MongoDB query
        start_of_day_utc = start_of_day.astimezone(pytz.UTC)
        end_of_day_utc = end_of_day.astimezone(pytz.UTC)
        
        # Build base query with date range
        query = {"event_date": {"$gte": start_of_day_utc, "$lt": end_of_day_utc}}
        
        # Debug: Check what sports are actually in the database
        distinct_sports = moneylines_collection.distinct('sport')
        logger.info(f"Available sports in database: {distinct_sports}")
        
        # Add sport filter if specified (using correct database format)
        if sports and isinstance(sports, list):
            sport_mapping = {
                'NBA': 'Basketball NBA',
                'NFL': 'American Football NFL',
                'NCAAB': 'Basketball NCAA',
                'NCAAF': 'American Football NCAA',
                'NHL': 'Ice Hockey NHL',
                'Basketball NBA': 'Basketball NBA',
                'American Football NFL': 'American Football NFL',
                'Basketball NCAA': 'Basketball NCAA',
                'American Football NCAA': 'American Football NCAA',
                'Ice Hockey NHL': 'Ice Hockey NHL'
            }
            mapped_sports = [sport_mapping[s] for s in sports if s in sport_mapping]
            if mapped_sports:
                query['sport'] = {'$in': mapped_sports}
        
        # Log the query and sample document
        logger.info(f"MongoDB Query: {query}")
        sample_game = moneylines_collection.find_one()
        logger.info(f"Sample game document: {sample_game}")
        
        total_games = moneylines_collection.count_documents(query)
        logger.info(f"Found {total_games} games matching query")
        
        if total_games == 0:
            return [], 0

        skip = (page - 1) * per_page
        games_cursor = moneylines_collection.find(query).skip(skip).limit(per_page)

        games = []
        for game in games_cursor:
            event_date_utc = game.get('event_date')
            if isinstance(event_date_utc, str):
                event_date_utc = datetime.fromisoformat(event_date_utc)
            if event_date_utc.tzinfo is None:
                event_date_utc = pytz.utc.localize(event_date_utc)
            event_date_local = event_date_utc.astimezone(user_timezone)

            games.append({
                'event_date': event_date_local,
                'home_team': game.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                'home_moneyline': game.get('teams', {}).get('home', {}).get('moneyline', 'N/A'),
                'away_team': game.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                'away_moneyline': game.get('teams', {}).get('away', {}).get('moneyline', 'N/A'),
                'winner': game.get('result', {}).get('winner', 'N/A'),
                'status': game.get('status', 'In Progress'),
                'result': {  # Add scores to the game data
                    'home_score': game.get('result', {}).get('home_score', 'N/A'),
                    'away_score': game.get('result', {}).get('away_score', 'N/A')
                }
            })

        games = sorted(games, key=lambda x: x['event_date'])
        return games, total_games
    except Exception as e:
        logger.error(f"Error in fetch_games function: {e}")
        return [], 0

def fetch_team_games(team, page=1, per_page=20):
    try:
        # Get user's timezone
        timezone = session.get('timezone', 'UTC')
        user_timezone = pytz.timezone(timezone)
        
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
        # Add sort parameter to find() call
        games_cursor = moneylines_collection.find(query).sort('event_date', -1).skip(skip).limit(per_page)

        # Process games
        games = []
        for game in games_cursor:
            event_date_utc = game.get('event_date')
            if isinstance(event_date_utc, str):
                event_date_utc = datetime.fromisoformat(event_date_utc)
            if event_date_utc.tzinfo is None:
                event_date_utc = pytz.utc.localize(event_date_utc)
            event_date_local = event_date_utc.astimezone(user_timezone)

            games.append({
                'event_date': event_date_local,
                'home_team': game.get('teams', {}).get('home', {}).get('name', 'Unknown'),
                'home_moneyline': game.get('teams', {}).get('home', {}).get('moneyline', 'N/A'),
                'away_team': game.get('teams', {}).get('away', {}).get('name', 'Unknown'),
                'away_moneyline': game.get('teams', {}).get('away', {}).get('moneyline', 'N/A'),
                'winner': game.get('result', {}).get('winner', 'N/A'),
                'status': game.get('status', 'In Progress'),
                'result': {  # Add scores to the game data
                    'home_score': game.get('result', {}).get('home_score', 'N/A'),
                    'away_score': game.get('result', {}).get('away_score', 'N/A')
                }
            })

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

# Add this after the app initialization, before the routes

@app.template_filter('format_datetime')
def format_datetime(value, timezone=None):
    """Format datetime to user's timezone and preferred format"""
    if not timezone:
        timezone = session.get('timezone', 'UTC')
    tz = pytz.timezone(timezone)
    # Ensure the datetime is timezone aware
    if value.tzinfo is None:
        value = pytz.utc.localize(value)
    # Convert to user timezone
    local_dt = value.astimezone(tz)
    # Format as mm/dd/yyyy hh:mm AM/PM
    return local_dt.strftime('%m/%d/%Y %I:%M %p')

# --------------------- Routes ---------------------
@app.route('/')
@login_required
def index():
    try:
        # Get user's timezone from session
        timezone = session.get('timezone', 'UTC')
        user_tz = pytz.timezone(timezone)
        
        # Get current time in user's timezone
        now_user_tz = datetime.now(user_tz)
        
        page = int(request.args.get('page', 1))
        selected_sports = request.args.getlist('sports') or ['NBA', 'NFL', 'NCAAB', 'NCAAF', 'NHL']
        
        games_today, total_games = fetch_games(
            target_date=now_user_tz, 
            timezone=timezone, 
            page=page, 
            per_page=10,
            sports=selected_sports
        )
        total_pages = (total_games + 10 - 1) // 10

        return render_template('today.html', 
                            games=games_today, 
                            page_title="Today's Games",
                            current_page=page, 
                            total_pages=total_pages, 
                            timezone=timezone,
                            selected_sports=selected_sports)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template('error.html', message="An error occurred while fetching today's games.")

@app.route('/tomorrow')
@login_required
def tomorrow():
    try:
        timezone = session.get('timezone', 'UTC')
        user_tz = pytz.timezone(timezone)
        now = datetime.now(user_tz)
        next_day_date = now + timedelta(days=1)
        
        page = int(request.args.get('page', 1))
        # Changed to default to NBA only if no sport is selected
        selected_sports = request.args.getlist('sports') or ['NBA']
        
        games_next_day, total_games = fetch_games(
            target_date=next_day_date,
            timezone=timezone,
            page=page,
            per_page=10,
            sports=selected_sports
        )
        total_pages = (total_games + 10 - 1) // 10

        return render_template('tomorrow.html',
                            games=games_next_day, 
                            page_title="Tomorrow's Games",
                            current_page=page, 
                            total_pages=total_pages, 
                            timezone=timezone,
                            selected_sports=selected_sports)
    except Exception as e:
        logger.error(f"Error in tomorrow route: {e}")
        return render_template('error.html', message="An error occurred while fetching tomorrow's games.")

@app.route('/yesterday')  # Changed from '/previous_games' to '/yesterday'
@login_required
def yesterday():  # Changed from 'previous_games' to 'yesterday'
    try:
        timezone = session.get('timezone', 'UTC')
        user_tz = pytz.timezone(timezone)
        now = datetime.now(user_tz)
        previous_day_date = now - timedelta(days=1)
        
        page = int(request.args.get('page', 1))
        selected_sports = request.args.getlist('sports') or ['NBA', 'NFL', 'NCAAB', 'NCAAF', 'NHL']
        
        games_previous_day, total_games = fetch_games(
            target_date=previous_day_date,
            timezone=timezone,
            page=page,
            per_page=10,
            sports=selected_sports
        )
        total_pages = (total_games + 10 - 1) // 10

        return render_template('yesterday.html',  # Changed from 'previous_games.html' to 'yesterday.html'
                            games=games_previous_day, 
                            page_title="Yesterday's Games",
                            current_page=page, 
                            total_pages=total_pages, 
                            timezone=timezone,
                            selected_sports=selected_sports)
    except Exception as e:
        logger.error(f"Error in yesterday route: {e}")  # Updated error message
        return render_template('error.html', message="An error occurred while fetching yesterday's games.")

@app.route('/team_stats', methods=['GET', 'POST'])
@login_required
def team_stats():
    try:
        # Get user's timezone
        timezone = session.get('timezone', 'UTC')
        
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
        underdog_wins = 0
        favored_wins = 0
        total_completed_underdog_games = 0
        total_completed_favored_games = 0
        total_underdog_games = 0
        total_favored_games = 0

        for game in games:
            # Determine if team is favored, regardless of game status
            if game['home_team'] == team:
                is_favored = game['home_moneyline'] < game['away_moneyline']
            else:
                is_favored = game['away_moneyline'] < game['home_moneyline']

            # Track total games
            if is_favored:
                total_favored_games += 1
            else:
                total_underdog_games += 1

            # Skip games that aren't completed for win statistics
            if game['status'] != 'Completed':
                continue

            # Track completed games and wins
            if is_favored:
                total_completed_favored_games += 1
                if game['winner'] == team:
                    favored_wins += 1
            else:
                total_completed_underdog_games += 1
                if game['winner'] == team:
                    underdog_wins += 1

        # Calculate percentages based only on completed games
        underdog_win_rate = (underdog_wins / total_completed_underdog_games * 100) if total_completed_underdog_games > 0 else 0
        favored_win_rate = (favored_wins / total_completed_favored_games * 100) if total_completed_favored_games > 0 else 0

        total_pages = (total_games + per_page - 1) // per_page

        return render_template(
            'team_stats.html',
            games=games,
            selected_team=team,
            teams=get_unique_teams(),
            page_title=f"Stats for {team}" if team else "Team Stats",
            current_page=page,
            total_pages=total_pages,
            underdog_win_rate=underdog_win_rate,
            favored_win_rate=favored_win_rate,
            total_underdog_games=total_underdog_games,
            total_favored_games=total_favored_games,
            total_completed_underdog_games=total_completed_underdog_games,
            total_completed_favored_games=total_completed_favored_games,
            underdog_wins=underdog_wins,
            favored_wins=favored_wins,
            timezone=timezone
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

            # Generate MongoDB query or aggregation pipeline
            result = query_generator.generate_query(natural_query)
            mongo_query = result['query']
            is_aggregation = result['is_aggregation']

            # Execute the query
            try:
                if is_aggregation:
                    # Execute aggregation pipeline
                    results = list(moneylines_collection.aggregate(mongo_query))
                else:
                    # Execute find query
                    results = list(moneylines_collection.find(mongo_query).limit(20))
            except Exception as e:
                logger.error(f"Error executing MongoDB query: {e}")
                logger.error(f"Generated Query: {mongo_query}")
                return render_template('search.html', error="Invalid query generated. Please try a different search.")

            # Log the results for debugging
            logger.info(f"Query results: {results}")

            # Render the results
            return render_template(
                'search.html',
                results=results,
                query=natural_query,
                is_aggregation=is_aggregation
            )

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

@app.route('/set_timezone', methods=['POST'])
def set_timezone():
    data = request.get_json()
    timezone = data.get('timezone', 'UTC')
    session['timezone'] = timezone
    return jsonify({'status': 'success'})

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
