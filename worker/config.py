import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import resend

resend.api_key = os.environ["RESEND_API_KEY"]

RECEIVING_ADDRESS = "stopshop@schedule.mileshilliard.com"

SAVE_DIRECTORY = Path("./received_schedules")

UPLOAD_DIR = Path("./uploads")

PROCESSED_FILE = Path("./processed_emails.json")

WHITELIST = {
    "skywiredvt@gmail.com",
    # Add more allowed addresses here:
    # "manager@example.com",
}
