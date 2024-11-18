import os
import subprocess
from datetime import datetime, timedelta
import pytz

# Constants for update scheduling
FIRST_GAME_TIME = datetime.utcnow().replace(hour=15, minute=0, second=0, microsecond=0)  # Example: 3 PM UTC
UPDATE_INTERVAL_HOURS = 3
END_OF_DAY_UTC = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)

def is_within_update_window():
    """
    Determines if the current time is within the valid update window.
    The window starts 3 hours after the first game of the day and ends at midnight UTC.
    """
    now = datetime.utcnow()
    start_time = FIRST_GAME_TIME + timedelta(hours=3)
    return start_time <= now <= END_OF_DAY_UTC

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
