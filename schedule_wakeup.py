import os
import csv
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client
from dotenv import load_dotenv

print("Scheduler started. Press Ctrl+C to exit.\n")
load_dotenv()

# 1. CONFIGURE YOUR PUBLISHED SHEET CSV URL
# Make sure you've published the form responses sheet as CSV.
CSV_URL = os.getenv("Google_Sheet_Link")

# 2. TWILIO CREDENTIALS
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

# Your Twilio Sandbox or WhatsApp-enabled number
from_whatsapp_number = "whatsapp:+14155238886"

# MAPPING: Receiver names from the form -> Actual WhatsApp phone numbers
RECEIVERS_MAP = {
    "Ekansh": "whatsapp:+916201524943",
    "KD":     "whatsapp:+918104621007",
    "Birla":  "whatsapp:+919518336220",
    "Tanmay":  "whatsapp:+917533918860",
    "MMS":    "whatsapp:+918588888094",
    "Deepu":  "whatsapp:+919461962606",
    "Kochar": "whatsapp:+918949467543",
    "Ninad":  "whatsapp:+917720040455",
    "Piyush":  "whatsapp:+917976933539",
    "Nick":  "whatsapp:+919719239619",
    "Anmol":  "whatsapp:+919343959758",
    "Bhat":    "whatsapp:+917774006757",
}

# 3. KEEP TRACK OF ALREADY-SCHEDULED ROWS (in-memory)
# If you restart the script, this set resets!
SCHEDULED_ROWS = set()

# 4. FUNCTION TO SEND THE WHATSAPP MESSAGE
def send_wakeup_message(name, location, importance, phone_numbers):
    """
    Sends the formatted WhatsApp message to all phone_numbers in the list.
    """
    message_body = f"*{name}* ko utha do, *{location}* pe so rha h. Bol rha tha ki *{importance}*."
    
    for number in phone_numbers:
        client.messages.create(
            body=message_body,
            from_=from_whatsapp_number,
            to=number
        )
        print(f"Sent message to {number} for {name} at {datetime.now()}\n")


def send_reminder_message(name, phone_numbers):
    """
    Sends a reminder message after the specified delay.
    """
    message_body = f"** Reminder! **\nCheck krlo ki *{name}* utha ki nhi."
    
    for number in phone_numbers:
        client.messages.create(
            body=message_body,
            from_=from_whatsapp_number,
            to=number
        )
        print(f"Sent reminder to {number} for {name} at {datetime.now()}\n")


# 5. SCHEDULE MESSAGES FOR EACH ROW IN THE SHEET
def schedule_all_messages():
    print(f"Fetching latest sheet data at {datetime.now()}\n")
    response = requests.get(CSV_URL)
    decoded_content = response.content.decode("utf-8")
    csv_data = list(csv.reader(decoded_content.splitlines(), delimiter=","))

    if len(csv_data) <= 1:
        print("No data found in the sheet.\n")
        return

    # Skip the header row (index 0)
    # Columns:
    #   0: Timestamp
    #   1: Name
    #   2: Wake-up Time (24H)
    #   3: Location
    #   4: Importance
    #   5: Receivers (comma-separated)
    #   6: Reminder delay

    for i, row in enumerate(csv_data[1:], start=1):
        # If this row has already been scheduled, skip
        if i in SCHEDULED_ROWS:
            continue

        # Ensure we have at least 7 columns
        if len(row) < 7:
            continue

        name = row[1]
        wakeup_time_str = row[2]
        location = row[3]
        importance = row[4]
        receivers_str = row[5]

        # Parse the wake-up time (e.g., "23:26:00" or "07:00")
        try:
            try:
                wake_time = datetime.strptime(wakeup_time_str, "%H:%M:%S").time()
            except ValueError:
                wake_time = datetime.strptime(wakeup_time_str, "%H:%M").time()
        except ValueError:
            print(f"Skipping invalid time format: {wakeup_time_str}\n")
            continue

        # Parse the receivers
        # If user selected multiple checkboxes, they'll be comma-separated in one string
        selected_receivers = [r.strip() for r in receivers_str.split(",") if r.strip()]

        # Convert receiver names to phone numbers using RECEIVERS_MAP
        phone_numbers = []
        for receiver_name in selected_receivers:
            if receiver_name in RECEIVERS_MAP:
                phone_numbers.append(RECEIVERS_MAP[receiver_name])
            else:
                print(f"Warning: No mapping found for receiver '{receiver_name}'\n")

        # If we have no valid phone numbers, skip scheduling
        if not phone_numbers:
            continue

        try:
            reminder_delay = int(row[6])
        except ValueError:
            print(f"Invalid reminder delay '{row[6]}' for row {i}, defaulting to 5 minutes.\n")
            reminder_delay = 5

        # Combine today's date with the parsed time
        now = datetime.now()
        target_dt = datetime(now.year, now.month, now.day, wake_time.hour, wake_time.minute, wake_time.second)

        # If that time is already passed today, schedule for tomorrow
        if target_dt <= now:
            target_dt += timedelta(days=1)

        # Schedule the job to run at 'target_dt'
        scheduler.add_job(
            send_wakeup_message,
            "date",
            run_date=target_dt,
            args=[name, location, importance, phone_numbers]
        )

        # Schedule the reminder after the custom delay (in minutes) from the new column
        reminder_dt = target_dt + timedelta(minutes=reminder_delay)
        scheduler.add_job(
            send_reminder_message,
            "date",
            run_date=reminder_dt,
            args=[name, phone_numbers]
        )

        # Mark this row as scheduled
        SCHEDULED_ROWS.add(i)

        print(f"Scheduled message for row {i} ({name}) at {target_dt} and reminder at {reminder_dt} (wake-up: {wakeup_time_str}, receivers: {selected_receivers})\n")

# 6. SET UP APSCHEDULER
scheduler = BackgroundScheduler()

# Run once at startup
schedule_all_messages()

# Re-run every 1 minute (adjust as needed) to catch new form entries
scheduler.add_job(schedule_all_messages, 'interval', minutes=15)

# Start the scheduler
scheduler.start()

try:
    # Keep the script running to allow scheduled jobs to execute
    while True:
        pass
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    print("Scheduler stopped.")
