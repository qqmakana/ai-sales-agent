"""Automated agent runner - runs the agent on a schedule."""
import schedule
import time
from cli import setup_agent

def run_agent():
    """Run the agent with a predefined goal."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting automated agent run...")
    controller = setup_agent()
    goal = "Email Sarah the daily summary"  # Change this to your desired goal
    result = controller.run(goal)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Agent completed: {result}")

# Schedule the agent to run daily at 9:00 AM
schedule.every().day.at("09:00").do(run_agent)

# Or schedule it to run every hour:
# schedule.every().hour.do(run_agent)

# Or schedule it to run every 30 minutes:
# schedule.every(30).minutes.do(run_agent)

# Or schedule it to run on specific days:
# schedule.every().monday.at("09:00").do(run_agent)

if __name__ == "__main__":
    print("Agent automation started. Press Ctrl+C to stop.")
    print("Scheduled to run daily at 9:00 AM")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute



