# **Multi-threaded Quotes Scraper Documentation**

## **Purpose**
This script scrapes quotes from multiple category pages using multithreading to improve efficiency. It stores the extracted data in MongoDB and provides an option to export the data to CSV and Excel.

### **Imported Libraries & Modules**
- `requests`: Sends HTTP requests to retrieve web pages.
- `lxml.html`: Parses HTML content and extracts data using XPath.
- `pymongo.MongoClient`: Connects to MongoDB for storing scraped data.
- `concurrent.futures.ThreadPoolExecutor`: Manages multiple threads for concurrent execution.
- `time`: Measures script execution time.
- `threading`: Implements thread-safe operations.
- `pandas`: Exports data to CSV and Excel files.

```python
# Import required modules
import requests
from lxml import html
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
import pandas as pd
```

## **User Inputs**
```python
request_limit = int(input("Enter the maximum number of requests to send: "))
max_workers = int(input("Enter the number of max workers (threads): "))
```
- `request_limit`: Maximum number of HTTP requests to send.
- `max_workers`: Number of concurrent threads to use.

## **MongoDB Connection**
```python
client = MongoClient('mongodb://localhost:27017/')
db = client['quotes_db']
category_collection = db['category_urls']
quotes_collection = db['quotes_details']
```
- Connects to MongoDB at `localhost:27017`.
- Uses `quotes_db` database and `category_urls` & `quotes_details` collections.

## **Fetching Pending Category Links**
```python
pending_categories = list(category_collection.find({"status": "pending"}).limit(900))
```
- Retrieves up to 900 pending category URLs from MongoDB.

## **Thread-Safe Request Counter**
```python
request_count = 0
request_lock = threading.Lock()
limit_reached_logged = False
```
- Uses `threading.Lock()` to prevent race conditions.
- Ensures that request limit logging occurs only once.

## **Category Processing Function**
```python
def process_category(category):
```
### **Purpose:**
- Fetches paginated URLs from a category.
- Extracts quotes, authors, and tags.
- Inserts data into MongoDB.
- Stops when the request limit is reached.

### **Steps:**
1. **Fetch Category URL & Initialize Page Count**
```python
category_link = category.get("page_url")
page_number = 1
```
2. **Thread-Safe Request Increment**
```python
with request_lock:
    if request_count >= request_limit:
        if not limit_reached_logged:
            print("⚠️ Request limit reached. Stopping further requests.")
            limit_reached_logged = True
        return
    request_count += 1
```
3. **Send Request & Parse Response**
```python
response = requests.get(paginated_url)
tree = html.fromstring(response.content)
```
4. **Extract Quotes & Save Data**
```python
data = []
for quote in quotes:
    quote_data = {
        "quote": quote.xpath('span[@class="text"]/text()')[0],
        "author": quote.xpath('span/small[@class="author"]/text()')[0],
        "tags": ' | '.join(quote.xpath('div[@class="tags"]/a[@class="tag"]/text()')),
        "category_link": paginated_url
    }
    data.append(quote_data)
quotes_collection.insert_many(data, ordered=False)
```
5. **Check for Pagination**
```python
next_page = tree.xpath('//li[@class="next"]/a/@href')
if not next_page:
    break
page_number += 1
```
6. **Update Category Status in MongoDB**
```python
category_collection.update_one({"_id": category["_id"]}, {"$set": {"status": "done"}})
```

## **Executing with ThreadPoolExecutor**
```python
start_time = time.time()

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(process_category, cat): cat for cat in pending_categories}
    for future in as_completed(futures):
        future.result()

end_time = time.time()
total_time = round(end_time - start_time, 2)
```
- Submits tasks for processing categories concurrently.
- Handles exceptions and waits for threads to complete.

## **Script Completion Summary**
```python
print("🏁 All categories processed!")
print(f"📊 Total Requests Sent: {request_count}")
print(f"⏱️ Total Execution Time: {total_time} sec")
```

## **Exporting Data to CSV & Excel**
```python
def export_data():
    data = list(quotes_collection.find({}, {"_id": 0}))
    if not data:
        print("⚠️ No data found to export.")
        return
    df = pd.DataFrame(data)
    df.to_csv("quotes_data.csv", index=False, encoding="utf-8")
    df.to_excel("quotes_data.xlsx", index=False)
    print("✅ Data exported successfully.")

export_data()
```
- Fetches all documents from MongoDB.
- Saves them as `quotes_data.csv` and `quotes_data.xlsx`.

## **Final Notes**
1. **Thread Safety:** Uses `threading.Lock()` to manage concurrent request count.
2. **Error Handling:** Ensures the script logs request limit reach and gracefully stops requests.
3. **Scalability:** Uses `ThreadPoolExecutor` for concurrent execution.
4. **Data Storage:** Stores scraped quotes in MongoDB and provides CSV & Excel export options.
