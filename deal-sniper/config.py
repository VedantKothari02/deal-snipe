from dotenv import load_dotenv
import os

load_dotenv()

API_ID = os.getenv("API_ID")
if API_ID is not None:
    API_ID = int(API_ID)
API_HASH = os.getenv("API_HASH")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID")

CHANNELS = [
    -1001412868909,  # DealBee Deals
    -1001346861267,  # DealzTrendz
    -1001493857075,  # Best Deals in India
    -1001596448068,  # DealBee Tips, Tricks & Loots
    -5013256582      # your test channel
]

DEAL_SCORE_THRESHOLD = 10
DRY_RUN = True
