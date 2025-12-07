import hashlib
import random
import time
import requests
import re
import json
import os
from collections import defaultdict, deque


class CountMinSketch:
    def __init__(self, epsilon=0.001, delta=0.01):
        self.epsilon = epsilon
        self.delta = delta

        self.width = int(2 / epsilon)
        self.depth = int(-1 * (random.random() * 100) or 10)

        self.table = [[0] * self.width for _ in range(self.depth)]
        self.hash_seeds = [random.randint(1, 1_000_000) for _ in range(self.depth)]

    def _hash(self, item, seed):
        item = item.encode("utf-8")
        hash_value = int(hashlib.sha256(item + str(seed).encode()).hexdigest(), 16)
        return hash_value % self.width

    def update(self, item):
        for i in range(self.depth):
            index = self._hash(item, self.hash_seeds[i])
            self.table[i][index] += 1

    def estimate(self, item):
        estimates = []
        for i in range(self.depth):
            index = self._hash(item, self.hash_seeds[i])
            estimates.append(self.table[i][index])
        return min(estimates)


API_URL = "https://dsa-project-news-api.onrender.com/live"
FETCH_INTERVAL = 3.5
TOP_K = 10
WINDOW_SIZE = 20

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "she'd",
    "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves",    "said", "says", "say", "report", "reports", "reported", "according",
    "according to", "breaking", "update", "live", "news", "story", "via",
    "source", "sources", "new", "latest", "today", "yesterday", "tomorrow",
    "week", "month", "year", "time", "analysis", "editor", "editorial",
    "exclusive", "media", "press", "statement", "officials", "authorities"
}

def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()

# ---- SLIDING WINDOW CMS ----
window = deque()  # holds last N CMS sketches

def process_text(text):
    cleaned = clean_text(text)
    words = cleaned.split()

    # create a new CMS for THIS news item
    cms = CountMinSketch()
    for w in words:
        if w not in STOPWORDS and len(w) > 2:
            cms.update(w)

    # add to sliding window
    window.append(cms)

    # maintain window size
    if len(window) > WINDOW_SIZE:
        window.popleft()

def get_trending_words():
    combined_counts = defaultdict(int)

    # merge frequencies across ALL CMS in window
    for cms in window:
        for word in list(combined_counts.keys()):
            combined_counts[word] += cms.estimate(word)

    # simpler version: track words manually (optional)
    return sorted(
        combined_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:TOP_K]


current_trending = {}  # stores the latest trending words


def get_top_k_words():
    """
    Get the current top K trending words from the background process
    
    Returns:
        Dictionary with word as key and probability as value
    """
    global current_trending
    
    if not current_trending:
        return {}
    
    # Convert to probabilities
    total = sum(current_trending.values())
    return {word: count / total for word, count in current_trending.items()} if total > 0 else {}

def fetch_live_news():
    try:
        response = requests.get(API_URL, timeout=5)
        if response.status_code != 200:
            return ""

        data = response.json()
        title = data.get("title", "")
        text = data.get("text", "")

        return f"{title} {text}"

    except Exception as e:
        print("⚠ API Error:", e)
        return ""


print("📡 Real-Time News Trend Detection Started")
print("Using a sliding window of last 5 news articles.\n")

all_words_buffer = []  # stores words for trending

def save_trending_to_file(trending_dict):
    """Save trending words to a JSON file for Streamlit to read"""
    try:
        output_file = os.path.join(os.path.dirname(__file__), "trending_words.json")
        with open(output_file, "w") as f:
            json.dump(trending_dict, f)
    except Exception as e:
        print(f"Error saving trending words: {e}")


def run_background_algorithm():
    """Main background loop that continuously fetches and processes news"""
    global current_trending
    
    try:
        while True:
            content = fetch_live_news()

            if content:
                print(f"\n🟦 NEW DATA RECEIVED:\n{content[:250]}...")

                cleaned = clean_text(content)
                words = [w for w in cleaned.split() if w not in STOPWORDS and len(w) > 2]

                # store last WINDOW_SIZE articles' words
                all_words_buffer.append(words)
                if len(all_words_buffer) > WINDOW_SIZE:
                    all_words_buffer.pop(0)

                # process using CMS window
                process_text(content)

                # calculate frequencies PER WINDOW
                freq_map = defaultdict(int)
                for article_words in all_words_buffer:
                    for w in article_words:
                        freq_map[w] += 1

                trending = sorted(freq_map.items(), key=lambda x: x[1], reverse=True)[:TOP_K]
                
                # Update global cache with current trending words
                current_trending = dict(trending)
                
                # Save to file for Streamlit to read
                save_trending_to_file(current_trending)

                print("\n🔥 TOP TRENDING WORDS (Fresh Window):")
                for word, freq in trending:
                    print(f"{word} → {freq}")

            else:
                print("⚠ No data received from API.")

            time.sleep(FETCH_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Program stopped by user.")


# Run the background algorithm if this is the main module
if __name__ == "__main__":
    run_background_algorithm()