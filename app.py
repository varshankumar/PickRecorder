import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import logging
import os
from flask_login import LoginManager, login_user, logout_user, login_required
from models import User
from config import SPORTS, GEMINI_API_KEY
from mongo_query_generator import MongoQueryGenerator

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

# --------------------- Helper Functions ---------------------
def get_team_stats(team):
    try:
        team = team.strip().lower()
        logger.info(f"Calculating stats for team: {team}")
        
        # Fetch completed games where the team participated
        completed_games = list(moneylines_collection.find({
            '$or': [
                {'teams.home.name': {'$regex': f'^{team}$', '$options': 'i'}},
                {'teams.away.name': {'$regex': f'^{team}$', '$options': 'i'}}
            ],
            'status': 'Completed'
        }))
        
        logger.info(f"Found {len(completed_games)} completed games for {team}")
        
        # Initialize counters
        favored_wins = 0
        underdog_wins = 0
        total_favored = 0
        total_underdog = 0
        
        # Process each game
        for game in completed_games:
            home_team = game.get('teams', {}).get('home', {}).get('name', '').strip()
            away_team = game.get('teams', {}).get('away', {}).get('name', '').strip()
            home_ml = game.get('teams', {}).get('home', {}).get('moneyline')
            away_ml = game.get('teams', {}).get('away', {}).get('moneyline')
            winner = game.get('result', {}).get('winner', '').strip()
            
            # Normalize team names
            home_team_lower = home_team.lower()
            away_team_lower = away_team.lower()
            winner_lower = winner.lower()
            
            # Ensure moneyline values are numbers
            try:
                home_ml = float(home_ml)
            except (TypeError, ValueError):
                home_ml = None
            try:
                away_ml = float(away_ml)
            except (TypeError, ValueError):
                away_ml = None
            
            # Skip game if moneylines are missing or invalid
            if home_ml is None or away_ml is None:
                logger.warning(f"Skipping game due to invalid moneylines: {home_team} vs {away_team}")
                continue
            
            # Determine if the team is home or away
            if home_team_lower == team:
                is_home = True
            elif away_team_lower == team:
                is_home = False
            else:
                logger.warning(f"{team} not found in game teams: {home_team} vs {away_team}")
                continue
            
            team_ml = home_ml if is_home else away_ml
            opp_ml = away_ml if is_home else home_ml
            
            # Compare moneylines to determine if team was favored or underdog
            if team_ml < opp_ml:
                total_favored += 1
                if winner_lower == team:
                    favored_wins += 1
                logger.info(f"{team} was favored - Result: {'Win' if winner_lower == team else 'Loss'}")
            elif team_ml > opp_ml:
                total_underdog += 1
                if winner_lower == team:
                    underdog_wins += 1
                logger.info(f"{team} was underdog - Result: {'Win' if winner_lower == team else 'Loss'}")
            else:
                # Moneylines are equal, skip or count as neither favored nor underdog
                logger.info(f"{team} had equal moneyline with opponent - Skipping this game")
        
        # Log final counts
        logger.info(f"Favored wins: {favored_wins} out of {total_favored}")
        logger.info(f"Underdog wins: {underdog_wins} out of {total_underdog}")
        
        # Calculate percentages, avoid division by zero
        stats = {
            'favored_win_rate': (favored_wins / total_favored * 100) if total_favored > 0 else 0,
            'underdog_win_rate': (underdog_wins / total_underdog * 100) if total_underdog > 0 else 0
        }
        
        logger.info(f"Calculated stats for {team}: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error calculating team stats for {team}: {e}", exc_info=True)
        return {'favored_win_rate': 0, 'underdog_win_rate': 0}

def calculate_win_stats(team, up_to_date=None):
    try:
        team = team.strip().lower()
        logger.info(f"Calculating win stats for team: {team} up to date: {up_to_date}")
        
        # Prepare the date filter if a date is provided
        date_filter = {'$lte': up_to_date} if up_to_date else {}
        
        # Fetch completed games where the team participated and before the specified date
        completed_games = list(moneylines_collection.find({
            '$and': [
                {'$or': [
                    {'teams.home.name': {'$regex': f'^{team}$', '$options': 'i'}},
                    {'teams.away.name': {'$regex': f'^{team}$', '$options': 'i'}}
                ]},
                {'status': 'Completed'},
                {'event_date': date_filter} if up_to_date else {}
            ]
        }))
        
        underdog_wins = 0
        favored_wins = 0
        total_completed_underdog_games = 0
        total_completed_favored_games = 0
        total_underdog_games = 0
        total_favored_games = 0

        for game in completed_games:
            home_team = game.get('teams', {}).get('home', {}).get('name', '').strip()
            away_team = game.get('teams', {}).get('away', {}).get('name', '').strip()
            home_moneyline = game.get('teams', {}).get('home', {}).get('moneyline')
            away_moneyline = game.get('teams', {}).get('away', {}).get('moneyline')
            winner = game.get('result', {}).get('winner', '').strip()

            # Normalize team names
            home_team_lower = home_team.lower()
            away_team_lower = away_team.lower()
            winner_lower = winner.lower()

            # Ensure moneyline values are numbers
            try:
                home_moneyline = float(home_moneyline)
            except (TypeError, ValueError):
                home_moneyline = None
            try:
                away_moneyline = float(away_moneyline)
            except (TypeError, ValueError):
                away_moneyline = None

            # Skip game if moneylines are missing or invalid
            if home_moneyline is None or away_moneyline is None:
                logger.warning(f"Skipping game due to invalid moneylines: {home_team} vs {away_team}")
                continue

            # Determine if team is home or away
            if home_team_lower == team:
                is_home = True
            elif away_team_lower == team:
                is_home = False
            else:
                logger.warning(f"{team} not found in game teams: {home_team} vs {away_team}")
                continue

            team_ml = home_moneyline if is_home else away_moneyline
            opp_ml = away_moneyline if is_home else home_moneyline

            # Compare moneylines to determine if team was favored or underdog
            if team_ml < opp_ml:
                total_favored_games += 1
                total_completed_favored_games += 1
                if winner_lower == team:
                    favored_wins += 1
            elif team_ml > opp_ml:
                total_underdog_games += 1
                total_completed_underdog_games += 1
                if winner_lower == team:
                    underdog_wins += 1
            else:
                logger.info(f"{team} had equal moneyline with opponent - Skipping this game")

        # Calculate win rates
        underdog_win_rate = (underdog_wins / total_completed_underdog_games * 100) if total_completed_underdog_games > 0 else 0
        favored_win_rate = (favored_wins / total_completed_favored_games * 100) if total_completed_favored_games > 0 else 0

        stats = {
            'underdog_win_rate': underdog_win_rate,
            'favored_win_rate': favored_win_rate,
            'underdog_wins': underdog_wins,
            'favored_wins': favored_wins,
            'total_completed_underdog_games': total_completed_underdog_games,
            'total_completed_favored_games': total_completed_favored_games,
            'total_underdog_games': total_underdog_games,
            'total_favored_games': total_favored_games
        }

        logger.info(f"Calculated win stats for {team}: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error in calculate_win_stats for {team}: {e}", exc_info=True)
        return {
            'underdog_win_rate': 0,
            'favored_win_rate': 0,
            'underdog_wins': 0,
            'favored_wins': 0,
            'total_completed_underdog_games': 0,
            'total_completed_favored_games': 0,
            'total_underdog_games': 0,
            'total_favored_games': 0
        }

def fetch_games(target_date, timezone=None, page=1, per_page=10, sports=None):
    try:
        timezone = timezone or session.get('timezone', 'UTC')
        user_timezone = pytz.timezone(timezone)
        utc = pytz.UTC
        
        # Make sure target_date is timezone aware in user's timezone
        if target_date.tzinfo is None:
            target_date = user_timezone.localize(target_date)
        
        # Get start and end of day in user's timezone
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convert to UTC for MongoDB query
        start_of_day_utc = start_of_day.astimezone(utc)
        end_of_day_utc = end_of_day.astimezone(utc)
        
        # Build query with strict date range
        base_query = {
            "event_date": {
                "$gte": start_of_day_utc,
                "$lte": end_of_day_utc
            }
        }

        # Add sport filter if specified
        if sports and isinstance(sports, list):
            query = {
                "$and": [
                    base_query,
                    {"sport": {"$in": sports}}
                ]
            }
        else:
            query = base_query

        # Debug logging
        logger.info(f"Query date range: {start_of_day_utc} to {end_of_day_utc}")
        logger.info(f"Target date: {target_date}")
        logger.info(f"Timezone: {timezone}")
        logger.info(f"Sports filter: {sports}")
        logger.info(f"Final query: {query}")

        # Execute query
        total_games = moneylines_collection.count_documents(query)
        logger.info(f"Found {total_games} games matching query")
        
        # Use proper sorting and pagination
        games_cursor = (moneylines_collection.find(query)
                       .sort('event_date', 1)
                       .skip((page - 1) * per_page)
                       .limit(per_page))
        
        games = []
        for game in games_cursor:
            event_date_utc = game.get('event_date')
            if isinstance(event_date_utc, str):
                event_date_utc = datetime.fromisoformat(event_date_utc)
            if event_date_utc.tzinfo is None:
                event_date_utc = pytz.utc.localize(event_date_utc)
            event_date_local = event_date_utc.astimezone(user_timezone)

            # Add team stats for in-progress games
            home_team_stats = None
            away_team_stats = None
            if game.get('status') == 'In Progress':
                home_team = game.get('teams', {}).get('home', {}).get('name')
                away_team = game.get('teams', {}).get('away', {}).get('name')
                home_team_stats = get_team_stats(home_team)
                away_team_stats = get_team_stats(away_team)

            home_team = game.get('teams', {}).get('home', {}).get('name', 'Unknown')
            away_team = game.get('teams', {}).get('away', {}).get('name', 'Unknown')
            # Fetch win stats for home and away teams
            home_team_stats = calculate_win_stats(home_team, up_to_date=event_date_utc)
            away_team_stats = calculate_win_stats(away_team, up_to_date=event_date_utc)

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
                },
                'home_team_stats': home_team_stats,
                'away_team_stats': away_team_stats
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

            # Add team stats for in-progress games
            home_team = game.get('teams', {}).get('home', {}).get('name', 'Unknown')
            away_team = game.get('teams', {}).get('away', {}).get('name', 'Unknown')
            home_team_stats = get_team_stats(home_team) if game.get('status') == 'In Progress' else None
            away_team_stats = get_team_stats(away_team) if game.get('status') == 'In Progress' else None

            # Fetch win stats as of the game date
            home_team_stats = calculate_win_stats(home_team, up_to_date=event_date_utc)
            away_team_stats = calculate_win_stats(away_team, up_to_date=event_date_utc)

            games.append({
                'event_date': event_date_local,
                'home_team': home_team,
                'home_moneyline': game.get('teams', {}).get('home', {}).get('moneyline', 'N/A'),
                'away_team': away_team,
                'away_moneyline': game.get('teams', {}).get('away', {}).get('moneyline', 'N/A'),
                'winner': game.get('result', {}).get('winner', 'N/A'),
                'status': game.get('status', 'In Progress'),
                'result': {  # Add scores to the game data
                    'home_score': game.get('result', {}).get('home_score', 'N/A'),
                    'away_score': game.get('result', {}).get('away_score', 'N/A')
                },
                'home_team_stats': home_team_stats,
                'away_team_stats': away_team_stats
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
        timezone = session.get('timezone', 'UTC')
        user_tz = pytz.timezone(timezone)
        now_user_tz = datetime.now(user_tz)
        
        page = int(request.args.get('page', 1))
        # Change this line to only default to NBA if no sports are explicitly selected
        selected_sports = request.args.getlist('sports')
        if not selected_sports:  # If no sports are selected in the URL
            selected_sports = ['NBA']  # Default to NBA only
        
        # Validate selected sports against config SPORTS values
        selected_sports = [sport for sport in selected_sports if sport in SPORTS.values()]
        if not selected_sports:
            selected_sports = ['NBA']
            
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
        
        # Calculate tomorrow's date at midnight in user's timezone
        now = datetime.now(user_tz)
        next_day_date = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # Debug logging
        logger.info(f"Fetching games for date: {next_day_date}")
        logger.info(f"User timezone: {timezone}")
        
        page = int(request.args.get('page', 1))
        selected_sports = request.args.getlist('sports') or ['NBA']
        
        # Debug log
        logger.info(f"Selected sports: {selected_sports}")
        
        games_next_day, total_games = fetch_games(
            target_date=next_day_date,
            timezone=timezone,
            page=page,
            per_page=10,
            sports=selected_sports
        )
        
        # Log results
        logger.info(f"Found {total_games} games for tomorrow")
        logger.info(f"Returning {len(games_next_day)} games for current page")
        
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
        # Change to match today/tomorrow default behavior
        selected_sports = request.args.getlist('sports')
        if not selected_sports:  # If no sports are selected in the URL
            selected_sports = ['NBA']  # Default to NBA only
        
        # Validate selected sports against config SPORTS values
        selected_sports = [sport for sport in selected_sports if sport in SPORTS.values()]
        if not selected_sports:
            selected_sports = ['NBA']
        
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

        # Fetch games for the selected team
        games, total_games = fetch_team_games(team, page=page, per_page=per_page) if team else ([], 0)

        # Calculate total pages for pagination
        total_pages = (total_games + per_page - 1) // per_page

        if team:
            # Calculate win statistics
            win_stats = calculate_win_stats(team)

            return render_template(
                'team_stats.html',
                games=games,
                selected_team=team,
                teams=get_unique_teams(),
                page_title=f"Stats for {team}",
                current_page=page,
                total_pages=total_pages,
                timezone=timezone,
                **win_stats  # Unpack the win_stats dictionary
            )
        else:
            return render_template('team_stats.html', teams=get_unique_teams())
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

            # Create query generator with API key
            query_generator = MongoQueryGenerator(gemini_api_key=GEMINI_API_KEY)
            result = query_generator.generate_query(prompt=natural_query)
            mongo_query = result['query']
            is_aggregation = result['is_aggregation']

            # Execute the query
            try:
                if is_aggregation:
                    results = list(moneylines_collection.aggregate(mongo_query))
                else:
                    results = list(moneylines_collection.find(mongo_query).limit(20))
            except Exception as e:
                logger.error(f"Error executing MongoDB query: {e}")
                logger.error(f"Generated Query: {mongo_query}")
                return render_template('search.html', error="Invalid query generated. Please try a different search.")

            logger.info(f"Query results: {results}")

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
