import os
import subprocess
from datetime import datetime, timedelta
import pytz

# Constants for update scheduling
PST_TZ = pytz.timezone('America/Los_Angeles')
START_TIME = datetime.now(PST_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
END_TIME = datetime.now(PST_TZ).replace(hour=22, minute=0, second=0, microsecond=0)
UPDATE_INTERVAL_HOURS = 1

def is_within_update_window():
    """
    Determines if the current time is within the valid update window (1 PM - 10 PM PST).
    """
    now = datetime.now(PST_TZ)
    current_date = now.date()
    start_time = START_TIME.replace(year=current_date.year, month=current_date.month, day=current_date.day)
    end_time = END_TIME.replace(year=current_date.year, month=current_date.month, day=current_date.day)
    return start_time <= now <= end_time

def run_update_game_results():
    """
    Executes the update_game_results.py script.
    """
    try:
        print("Running update_game_results.py...")
        subprocess.run(["python", "update_game_results.py"], check=True)
        print("update_game_results.py completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while running update_game_results.py: {e}")

def main():
    if is_within_update_window():
        print("Within update window. Proceeding to update game results...")
        run_update_game_results()
    else:
        print("Outside update window. Skipping update.")

if __name__ == "__main__":
    main()
