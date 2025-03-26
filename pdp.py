import requests
from lxml import html
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
import pandas as pd  # ✅ Added for CSV & Excel export

# 📝 **User Inputs**
request_limit = int(input("Enter the maximum number of requests to send: "))  # Example: 1000
max_workers = int(input("Enter the number of max workers (threads): "))  # Example: 50

# 1️⃣ **Connect to MongoDB**
client = MongoClient('mongodb://localhost:27017/')
db = client['quotes_db']
category_collection = db['category_urls']
quotes_collection = db['quotes_details']

# 2️⃣ **Fetch Pending Category Links**
pending_categories = list(category_collection.find({"status": "pending"}).limit(900))

if not pending_categories:
    print("⚠️ No pending categories found.")
    exit()

print(f"🚀 Found {len(pending_categories)} pending categories. Processing...")

# **Thread-Safe Request Counter**
request_count = 0
request_lock = threading.Lock()
limit_reached_logged = False  # To prevent duplicate log messages

def process_category(category):
    """
    Scrapes quotes from a category page until the request limit is reached.

    Args:
        category (dict): The category document containing `page_url` from MongoDB.

    Behavior:
        - Fetches paginated URLs for a category.
        - Extracts quotes, authors, and tags.
        - Inserts data into MongoDB.
        - Stops when the request limit is reached.
    """
    global request_count, limit_reached_logged
    category_link = category.get("page_url")

    if not category_link:
        return

    page_number = 1
    while True:
        with request_lock:
            if request_count >= request_limit:
                if not limit_reached_logged:
                    print("⚠️ Request limit reached. Stopping further requests.")
                    limit_reached_logged = True  # Log only once
                return  # Stop this thread

            # **Increment count inside lock BEFORE sending request**
            request_count += 1
            current_request_number = request_count  # Store for print

        paginated_url = f"{category_link}/page/{page_number}/"
        print(f"📌 Request #{current_request_number}: {paginated_url}")  # Print Request Number

        response = requests.get(paginated_url)

        if response.status_code != 200:
            break

        tree = html.fromstring(response.content)
        quotes = tree.xpath('//div[@class="quote"]')

        data = []  # List to store dictionaries for this page

        for quote in quotes:
            # **Create a dictionary for each quote**
            quote_data = {
                "quote": quote.xpath('span[@class="text"]/text()')[0],
                "author": quote.xpath('span/small[@class="author"]/text()')[0],
                "tags": ' | '.join(quote.xpath('div[@class="tags"]/a[@class="tag"]/text()')),
                "category_link": paginated_url
            }

            # **Append the dictionary to the data list**
            data.append(quote_data)

        # **Bulk Insert Data into MongoDB**
        if data:
            quotes_collection.insert_many(data, ordered=False)

        # Check for "Next" button to continue pagination
        next_page = tree.xpath('//li[@class="next"]/a/@href')
        if not next_page:
            break

        page_number += 1

    # **Update Category Status**
    category_collection.update_one({"_id": category["_id"]}, {"$set": {"status": "done"}})


# 6️⃣ **Execute Using ThreadPoolExecutor**
start_time = time.time()

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    """
    Creates a thread pool to process multiple categories concurrently.

    - Submits `process_category` tasks to the thread pool.
    - Waits for all threads to complete.
    - Handles any exceptions that might occur.
    """
    futures = {executor.submit(process_category, cat): cat for cat in pending_categories}

    for future in as_completed(futures):
        future.result()  # Ensure exceptions are raised if any

end_time = time.time()
total_time = round(end_time - start_time, 2)

print("🏁 All categories processed!")
print(f"📊 Total Requests Sent: {request_count}")  # Should be exactly 1000
print(f"⏱️ Total Execution Time: {total_time} sec")


# ✅ **EXPORT FUNCTION: Save Data to CSV & Excel**
def export_data():
    """
    Exports the scraped data from MongoDB to CSV and Excel files.

    Behavior:
        - Fetches all documents from `quotes_dattta` collection.
        - Saves the data to `quotes_data.csv` and `quotes_data.xlsx`.
        - Skips export if no data is found.
    """
    data = list(quotes_collection.find({}, {"_id": 0}))  # Fetch all data from MongoDB

    if not data:
        print("⚠️ No data found to export.")
        return

    df = pd.DataFrame(data)

    # Save as CSV
    csv_filename = "quotes_data.csv"
    df.to_csv(csv_filename, index=False, encoding="utf-8")
    print(f"✅ Data exported to CSV: {csv_filename}")

    # Save as Excel
    excel_filename = "quotes_data.xlsx"
    df.to_excel(excel_filename, index=False)
    print(f"✅ Data exported to Excel: {excel_filename}")

# **Call Export Function**
export_data()
