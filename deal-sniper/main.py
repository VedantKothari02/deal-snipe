import asyncio
import logging
import os
import signal
import sys
sys.stdout.reconfigure(encoding="utf-8")

import requests


# 1. Initialize logging before any other subsystem
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/deal_sniper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("main")

from config import DEAL_SCORE_THRESHOLD
from database import init_db, check_duplicate, record_alert, record_price_history
from listeners.telegram_listener import start_listener
from parsers.link_extractor import extract_links
from parsers.deal_parser import parse_deal
from engine.deal_scorer import score_deal
from engine.job_queue import JobQueue
from watchers import amazon_watcher, flipkart_watcher, myntra_watcher, ajio_watcher
from notifier.telegram_bot import send_alert

# Global state
queue = JobQueue()
session = requests.Session()
worker_task = None

def get_watcher_for_site(site: str):
    if site == "amazon":
        return amazon_watcher.fetch_product_data
    elif site == "flipkart":
        return flipkart_watcher.fetch_product_data
    elif site == "myntra":
        return myntra_watcher.fetch_product_data
    elif site == "ajio":
        return ajio_watcher.fetch_product_data
    return None

def on_message(message_text: str):

    if not message_text:
        return

    links = extract_links(message_text)[:10]

    for link in links:
        try:
            parsed_data = parse_deal(message_text, link)
            
            logger.info(f"Parsed deal: {parsed_data}")
            
            if not parsed_data or parsed_data["site"] == "unknown":
                continue

            quick_score = score_deal(parsed_data)

            if quick_score >= DEAL_SCORE_THRESHOLD:
                logger.info(f"Queuing deal: {parsed_data['product_name']} | Score {quick_score}")

                loop = asyncio.get_running_loop()
                loop.create_task(queue.put(parsed_data))

            else:
                logger.info(f"Deal discarded due to low score ({quick_score}): {parsed_data['url']}")

        except Exception as e:
            logger.error(f"Error processing link {link}: {e}")



async def verification_worker():
    """
    Background worker that fetches product data using watchers.
    """
    logger.info("Verification worker started.")
    while True:
        try:
            job = await queue.get()
            url = job.get('url')
            site = job.get('site')
            product_id = job.get('product_id')

            fetch_func = get_watcher_for_site(site)
            if not fetch_func:
                logger.warning(f"No watcher found for site {site}")
                queue.task_done()
                continue

            # Run the synchronous fetch_func in an executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            product_data = await loop.run_in_executor(None, fetch_func, url, session)

            if not product_data:
                logger.warning(f"Failed to fetch data for {url}. Deal discarded.")
                queue.task_done()
                continue

            # Store the observed price history
            record_price_history(product_id, site, product_data['price'])

            # Recompute score with actual data
            merged_data = job.copy()
            merged_data.update({
                'price': product_data['price'],
                'mrp': product_data['mrp'],
                'product_name': product_data['product_name']
            })

            if merged_data['mrp'] > 0:
                merged_data['discount'] = round(((merged_data['mrp'] - merged_data['price']) / merged_data['mrp']) * 100, 2)
            else:
                merged_data['discount'] = 0

            final_score = score_deal(merged_data)

            if final_score >= DEAL_SCORE_THRESHOLD:
                # Check duplicates
                if check_duplicate(product_id, site, minutes=30):
                    logger.info(f"Duplicate alert prevented for {site} - {product_id}")
                else:
                    # Send and record alert
                    send_alert(merged_data, final_score)
                    record_alert(product_id, site, merged_data['price'])
            else:
                logger.info(f"Deal failed final score verification ({final_score}): {url}")

            queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker encountered an error: {e}")

def shutdown_handler(sig, frame):
    logger.info("Shutdown signal received. Cleaning up...")
    session.close()
    sys.exit(0)

async def main():
    # Graceful shutdown signals
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # 2. Init DB
    init_db()

    # 3. Start worker task
    global worker_task
    worker_task = asyncio.create_task(verification_worker())

    # 4. Start listener
    logger.info("Starting Telegram listener...")
    await start_listener(on_message)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting...")
    except Exception as e:
        logger.error(f"Application crash: {e}")
