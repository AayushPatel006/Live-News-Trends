import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import threading
from collections import defaultdict
from datetime import datetime
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import sys
import os

# Add the current directory to path to import core_algorithm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the function that fetches trending words from background process
from core_algorithm import get_top_k_words
import json

# Set up page config
st.set_page_config(
    page_title="Live News Feed with Word Analysis",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📰 Live News Feed with Word Probability Analysis")

# Start background algorithm process on app load
@st.cache_resource
def start_background_algorithm():
    """Start the core algorithm in a background thread"""
    import subprocess
    import sys
    
    # Start core_algorithm.py as a subprocess
    process = subprocess.Popen(
        [sys.executable, "core_algorithm.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return process

try:
    bg_process = start_background_algorithm()
except:
    pass  # Process might already be running

# Initialize session state for auto-refresh
if 'last_auto_fetch' not in st.session_state:
    st.session_state.last_auto_fetch = 0

if 'news_data' not in st.session_state:
    st.session_state.news_data = []

if 'last_fetch_time' not in st.session_state:
    st.session_state.last_fetch_time = None

if 'word_probabilities' not in st.session_state:
    st.session_state.word_probabilities = {}

if 'server_live' not in st.session_state:
    st.session_state.server_live = False

API_URL = "https://dsa-project-news-api.onrender.com/live"
FETCH_INTERVAL = 3.5  # seconds

def fetch_news():
    """Fetch latest news from the API"""
    try:
        response = requests.get(API_URL, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API returned status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching news: {e}")
        return None

def calculate_word_probabilities(news_articles):
    """
    Get word probabilities from the background core_algorithm process
    by reading from the JSON file it writes to
    """
    try:
        # Try to read trending words from file
        trending_file = os.path.join(os.path.dirname(__file__), "trending_words.json")
        if os.path.exists(trending_file):
            with open(trending_file, "r") as f:
                trending_dict = json.load(f)
            
            # Convert to probabilities
            if trending_dict:
                total = sum(trending_dict.values())
                return {word: count / total for word, count in trending_dict.items()} if total > 0 else {}
        return {}
    except Exception as e:
        print(f"Error fetching from algorithm: {e}")
        return {}

def create_word_probability_chart(word_probs):
    """Create a bar chart for word probabilities"""
    if not word_probs:
        st.warning("No word probability data available")
        return
    
    df = pd.DataFrame(list(word_probs.items()), columns=['Word', 'Probability'])
    df = df.sort_values('Probability', ascending=True)
    
    fig = px.bar(
        df,
        x='Probability',
        y='Word',
        orientation='h',
        title='Top 10 Words by Probability',
        labels={'Probability': 'Probability', 'Word': 'Word'},
        color='Probability',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        height=500,
        showlegend=False,
        xaxis_title="Probability",
        yaxis_title="Word"
    )
    
    return fig

def create_wordcloud(word_probs):
    """Create a word cloud from word probabilities"""
    if not word_probs:
        return None
    
    # Generate word cloud
    wc = WordCloud(
        width=1200,
        height=600,
        background_color='white',
        colormap='viridis',
        relative_scaling=0.5,
        min_font_size=10
    ).generate_from_frequencies(word_probs)
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    plt.tight_layout(pad=0)
    
    return fig

# Sidebar controls
st.sidebar.header("⚙️ Controls")

manual_fetch = st.sidebar.button("🔄 Fetch Now", key="manual_fetch")

# Auto-fetch news every 3.5 seconds using simple polling
current_time = time.time()
time_since_last_fetch = current_time - st.session_state.last_auto_fetch

# Fetch if manual button clicked or 3.5 seconds have passed
if manual_fetch or time_since_last_fetch >= FETCH_INTERVAL:
    news_data = fetch_news()
    st.session_state.last_auto_fetch = current_time
    
    if news_data:
        st.session_state.news_data = news_data if isinstance(news_data, list) else [news_data]
        st.session_state.last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.server_live = True
        
        # Calculate word probabilities from fetched news
        st.session_state.word_probabilities = calculate_word_probabilities(st.session_state.news_data)
    else:
        st.session_state.server_live = False
    
    # Schedule next rerun after 3.5 seconds
    import streamlit.runtime.app_session as app_session_module
    ctx = st.runtime.scriptrunner.get_script_run_ctx()
    if ctx:
        ctx.session_state._rerun_after_delay = True

# Display server status in sidebar
st.sidebar.divider()
if st.session_state.server_live:
    st.sidebar.success("🟢 Server is live")
    if st.session_state.last_fetch_time:
        st.sidebar.caption(f"Last updated: {st.session_state.last_fetch_time}")
else:
    if st.session_state.last_fetch_time:  # Only show error if we've tried to fetch
        st.sidebar.error("🔴 Server not live")

# Display latest news on top
st.subheader("Latest News")

if st.session_state.news_data:
    for i, article in enumerate(st.session_state.news_data[:5], 1):  # Show top 5
        with st.container(border=True):
            st.markdown(f"<h2 style='font-size: 24px;'>{article.get('title', 'No title')}</h2>", unsafe_allow_html=True)
            st.write(article.get('text', 'N/A')[:400] + "...")  # Show first 300 chars
            
            # Display categories
            categories = article.get('categories', [])
            if categories:
                category_tags = " | ".join([f"🏷️ {cat}" for cat in categories])
                st.caption(category_tags)
            
            if article.get('url'):
                st.write(f"[🔗 Read Full Article]({article.get('url')})")
            
            # Display author
            if article.get('author'):
                st.caption(f"✍️ Author: {article.get('author')}")
else:
    st.info("👈 Click 'Fetch Now' to load news articles!")

st.markdown("---")

# Single tab for word analysis
st.subheader("🗞️ Analysis")

if st.session_state.word_probabilities:
    # Display top words prominently
    top_words = list(st.session_state.word_probabilities.items())[:10]
    
    # Create columns for word display - 10 columns for horizontal layout
    cols = st.columns(10)
    for idx, (word, prob) in enumerate(top_words):
        with cols[idx]:
            st.markdown(f"""
            <div style="text-align: center;">
                <p style="font-size: 16px; font-weight: bold; margin: 0;">{word.upper()}</p>
                <p style="font-size: 12px; margin: 0;">{prob:.1%}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")

    # Create two columns for visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Word Cloud Visualization")
        wc_fig = create_wordcloud(st.session_state.word_probabilities)
        if wc_fig:
            st.pyplot(wc_fig)
    
    with col2:
        st.write("### Top Words by Probability")
        # Bar chart of top words
        fig = create_word_probability_chart(st.session_state.word_probabilities)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👈 Click 'Fetch Now' to get started with word analysis!")

# st.markdown("---")
# st.caption("💡 Tip: News is automatically fetched every 3.5 seconds. Use the 'Fetch Now' button for manual refresh. Integrate your algorithm in the `calculate_word_probabilities()` function.")

# Note: Auto-rerun disabled to prevent duplicate visualizations
# The background algorithm continuously updates trending_words.json
# Uncomment below to enable auto-refresh every 3.5 seconds
time.sleep(3.5)
st.rerun()
