import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os

from services.config import AppConfig
from data.scraping.reddit_client import RedditClient, RedditPost
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def render_header():
    st.markdown("## Predictive Virality and Topic-Trend Analysis")
    st.caption(
        "Explore trending topics, score headline virality, and gain insights from subreddit data."
    )
    st.divider()


# ---------------------------
# Mock data generators (UI demo)
# ---------------------------

def _get_trending_keywords(subreddits: List[str], time_window: str, limit: int = 50) -> Dict[str, float]:
    """
    Extract trending keywords from the specified subreddits.
    
    Args:
        subreddits: List of subreddits to analyze
        time_window: Time window for analysis ('24h', '7d', '30d')
        limit: Maximum number of posts to analyze
        
    Returns:
        Dictionary of keywords and their importance scores (0-1)
    """
    try:
        # Get trending posts
        df = _get_trending_posts(subreddits, time_window, limit)
        if df.empty:
            return {}
        
        # Combine titles and selftext for analysis
        all_text = ' '.join(df['title'].fillna('').astype(str) + ' ' + 
                           df['selftext'].fillna('').astype(str))
        
        # Use TF-IDF to extract important terms
        from sklearn.feature_extraction.text import TfidfVectorizer
        import nltk
        from nltk.corpus import stopwords
        from nltk.tokenize import word_tokenize
        import string
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('punkt')
            nltk.download('stopwords')
        
        # Custom tokenizer that removes stopwords and punctuation
        def custom_tokenizer(text):
            stop_words = set(stopwords.words('english'))
            tokens = word_tokenize(text.lower())
            tokens = [word for word in tokens if word not in stop_words 
                     and word not in string.punctuation
                     and len(word) > 2
                     and not word.isnumeric()]
            return tokens
        
        # Calculate TF-IDF scores
        vectorizer = TfidfVectorizer(
            tokenizer=custom_tokenizer,
            max_features=100,
            ngram_range=(1, 2)  # Include unigrams and bigrams
        )
        
        # Fit and transform the text data
        tfidf_matrix = vectorizer.fit_transform([all_text])
        feature_names = vectorizer.get_feature_names_out()
        tfidf_scores = tfidf_matrix.toarray()[0]
        
        # Create a dictionary of terms and their scores
        term_scores = dict(zip(feature_names, tfidf_scores))
        
        # Normalize scores to 0-1 range
        if term_scores:
            max_score = max(term_scores.values())
            term_scores = {k: v / max_score for k, v in term_scores.items()}
        
        return term_scores
        
    except Exception as e:
        logger.error(f"Error in _get_trending_keywords: {e}")
        return {}


def _mock_trending_df(n_topics: int = 10, periods: int = 14):
    dates = pd.date_range(end=pd.Timestamp.today(), periods=periods)
    topics = [f"Topic {i+1}" for i in range(n_topics)]
    data = []
    rng = np.random.default_rng(42)
    for t in topics:
        base = rng.integers(20, 200)
        noise = rng.normal(0, base * 0.15, size=periods).clip(min=-base * 0.5)
        series = (base + np.linspace(-base*0.3, base*0.4, periods) + noise).clip(min=0)
        for d, v in zip(dates, series):
            data.append({"date": d, "topic": t, "mentions": int(v)})
    return pd.DataFrame(data)


def _analyze_headline_virality(headline: str, subreddits: List[str] = None, time_window: str = '7d') -> dict:
    """
    Analyze a headline's potential virality with multiple metrics.
    
    Args:
        headline: The headline to analyze
        subreddits: List of target subreddits for context
        time_window: Time window for trend analysis ('24h', '7d', '30d')
        
    Returns:
        Dictionary containing virality metrics, sentiment, and suggestions
    """
    from textblob import TextBlob
    import re
    from collections import defaultdict
    
    # Initialize metrics with all required keys
    metrics = {
        'length_score': min(1.0, len(headline) / 100),  # 0-1 score based on length (optimal ~50-70 chars)
        'sentiment': 0.5,  # Neutral to start
        'sentiment_magnitude': 0,
        'word_count': len(headline.split()),
        'trend_score': 0.0,  # Will be calculated based on trend matches
        'trend_matches': [],  # Will store matching trending terms
        'keyword_scores': defaultdict(float),  # Track individual keyword scores
        'has_question': 1 if '?' in headline else 0,
        'has_exclamation': 1 if '!' in headline else 0,
        'has_number': 1 if any(char.isdigit() for char in headline) else 0,
        'has_emoji': 1 if any(ord(c) > 127 for c in headline) else 0,
        'all_caps_ratio': sum(1 for c in headline if c.isupper()) / len(headline) if headline else 0,
        'avg_word_length': sum(len(word) for word in headline.split()) / len(headline.split()) if headline.split() else 0,
    }
    
    # Get trending keywords for the specified time window
    trending_keywords = _get_trending_keywords(subreddits or [], time_window)
    
    # Analyze trend relevance if we have trending data
    if trending_keywords:
        headline_lower = headline.lower()
        total_score = 0
        matched_terms = []
        
        # Check for exact matches in trending keywords
        for term, score in trending_keywords.items():
            if term in headline_lower:
                metrics['keyword_scores'][term] = score
                matched_terms.append((term, score))
                total_score += score
        
        # Check for partial matches (individual words in n-grams)
        if len(matched_terms) < 3:  # Only check for partials if we don't have many exact matches
            headline_terms = set(re.findall(r'\b\w+\b', headline_lower))
            for term, score in trending_keywords.items():
                if term not in metrics['keyword_scores']:  # Skip already matched terms
                    term_words = set(term.split())
                    if len(term_words) > 1:  # Only check n-grams (not single words)
                        matching_words = headline_terms.intersection(term_words)
                        if matching_words:
                            partial_score = (len(matching_words) / len(term_words)) * score * 0.7
                            metrics['keyword_scores'][term] = partial_score
                            matched_terms.append((term, partial_score))
                            total_score += partial_score
        
        # Update trend score (normalized to 0-1 range)
        if matched_terms:
            metrics['trend_matches'] = sorted(matched_terms, key=lambda x: x[1], reverse=True)
            metrics['trend_score'] = min(1.0, total_score * 0.5)  # Cap at 1.0
    
    # Sentiment analysis
    blob = TextBlob(headline)
    metrics['sentiment'] = (blob.sentiment.polarity + 1) / 2  # Convert from -1:1 to 0:1
    metrics['sentiment_magnitude'] = blob.sentiment.subjectivity
    
    # Calculate virality score (0-100 scale)
    score = 50  # Base score
    
    # Adjust based on metrics (weights can be tuned)
    score += metrics['length_score'] * 10  # Length matters, but not too much
    score += metrics['sentiment'] * 5      # Positive sentiment helps
    score += metrics['sentiment_magnitude'] * 5  # Strong sentiment (positive or negative) helps
    score += metrics['has_question'] * 5   # Questions drive engagement
    score += metrics['has_exclamation'] * 3  # But too many look spammy
    score += metrics['has_number'] * 4     # Numbers work well
    score += metrics['has_emoji'] * 4      # Emojis help but can be overdone
    score -= metrics['all_caps_ratio'] * 20  # Too many caps hurt
    
    # Normalize score to 0-100 range
    score = max(0, min(100, score))
    
    # Generate insights
    top_features = [
        {"Metric": "Length", "Score": f"{metrics['length_score']*100:.0f}/100", "Impact": "Optimal: 50-70 chars"},
        {"Metric": "Sentiment", "Score": f"{metrics['sentiment']*100:.0f}/100", "Impact": "Higher is more positive"},
        {"Metric": "Engagement", "Score": f"{metrics['sentiment_magnitude']*100:.0f}/100", "Impact": "Higher means more emotionally engaging"},
        {"Metric": "Word Count", "Score": metrics['word_count'], "Impact": "Optimal: 10-15 words"},
    ]
    
    # Generate suggestions
    tips = []
    if metrics['length_score'] < 0.4:
        tips.append("📏 Your headline is too short. Aim for 50-70 characters.")
    elif metrics['length_score'] > 0.8:
        tips.append("📏 Your headline is too long. Consider making it more concise.")
        
    if metrics['sentiment'] < 0.4:
        tips.append("😔 Your headline is quite negative. Consider a more positive tone.")
    elif metrics['sentiment'] > 0.8:
        tips.append("😊 Great positive tone! This can drive engagement.")
        
    if metrics['word_count'] < 8:
        tips.append("📝 Add more context to your headline. 10-15 words often perform best.")
    elif metrics['word_count'] > 18:
        tips.append("✂️ Your headline is wordy. Try to be more concise.")
        
    if not metrics['has_number']:
        tips.append("🔢 Consider adding a number (e.g., '5 Ways to...' or '10 Tips for...')")
        
    if not any([metrics['has_question'], metrics['has_exclamation']]):
        tips.append("❓ Try adding a question or exclamation to increase engagement.")
    
    return {
        'score': round(score, 1),
        'metrics': metrics,
        'features': top_features,
        'suggestions': tips if tips else ["👍 Great headline! It has good potential for virality."]
    }


# ---------------------------
# Tabs
# ---------------------------

def _get_trending_posts(subreddits: List[str], time_window: str, limit: int = 50) -> pd.DataFrame:
    """Fetch trending posts from specified subreddits."""
    reddit = _get_reddit_client()
    if not reddit:
        return pd.DataFrame()
    
    try:
        all_posts = []
        
        # If no subreddits specified, get popular posts from all
        if not subreddits:
            subreddits = ['all']
        
        for subreddit in subreddits:
            try:
                # Get hot posts from the subreddit
                posts = reddit.get_subreddit_posts(
                    subreddit=subreddit,
                    limit=limit,
                    sort='hot',
                    time_filter='day' if time_window == '24h' else 'week' if time_window == '7d' else 'month'
                )
                
                for post in posts:
                    all_posts.append({
                        'title': post.title,
                        'subreddit': post.subreddit,
                        'score': post.score,
                        'num_comments': post.num_comments,
                        'url': post.url,
                        'permalink': post.permalink,
                        'created_utc': post.created_utc,
                        'created_date': datetime.utcfromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        'author': str(post.author) if post.author else '[deleted]',
                        'selftext': post.selftext
                    })
            except Exception as e:
                logger.warning(f"Error fetching posts from r/{subreddit}: {e}")
                continue
        
        return pd.DataFrame(all_posts) if all_posts else pd.DataFrame()
    
    except Exception as e:
        logger.error(f"Error in _get_trending_posts: {e}")
        return pd.DataFrame()

def _extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """Extract top N keywords from text using simple frequency analysis."""
    if not text:
        return []
    
    # Remove common words and tokenize
    stop_words = set(['the', 'and', 'to', 'of', 'a', 'in', 'for', 'is', 'on', 'that', 'with', 'was', 'it', 'as', 'at',
                     'by', 'be', 'this', 'are', 'from', 'or', 'an', 'your', 'you', 'we', 'our', 'us', 'i', 'me', 'my', 'mine'])
    
    words = [word.lower() for word in str(text).split() 
             if word.isalpha() and word.lower() not in stop_words and len(word) > 2]
    
    # Count word frequencies
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top N words by frequency
    return [w[0] for w in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]]

def render_dashboard_tab(subreddits: List[str], time_window: str):
    st.subheader("📊 Dashboard")
    
    # Show loading state
    with st.spinner('Fetching trending topics from Reddit...'):
        # Get trending posts
        df = _get_trending_posts(subreddits, time_window)
    
    if df.empty:
        st.warning("No trending posts found. Try adjusting your subreddit selection or time window.")
        return
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Subreddits", len(subreddits) if subreddits else "All")
    with col2:
        st.metric("Time Window", time_window)
    with col3:
        st.metric("Trending Posts", len(df))
    
    # Extract and analyze keywords from titles
    df['keywords'] = df['title'].apply(lambda x: _extract_keywords(x, top_n=3))
    
    # Create a row for each keyword in each post
    keyword_rows = []
    for _, row in df.iterrows():
        for kw in row['keywords']:
            keyword_rows.append({
                'keyword': kw,
                'score': row['score'],
                'num_comments': row['num_comments'],
                'subreddit': row['subreddit'],
                'created_date': row['created_date']
            })
    
    keyword_df = pd.DataFrame(keyword_rows)
    
    if not keyword_df.empty:
        # Top trending keywords
        st.write("### Trending Keywords")
        top_keywords = keyword_df.groupby('keyword').agg({
            'score': 'sum',
            'num_comments': 'sum',
            'subreddit': 'nunique'
        }).sort_values('score', ascending=False).head(10).reset_index()
        
        # Display top keywords as badges with metrics
        cols = st.columns(5)
        for i, (_, row) in enumerate(top_keywords.iterrows()):
            with cols[i % 5]:
                st.metric(
                    label=row['keyword'],
                    value=f"{row['score']:,}",
                    delta=f"{row['subreddit']} subreddits"
                )
        
        # Top posts by engagement
        st.write("### Top Posts by Engagement")
        top_posts = df.sort_values('score', ascending=False).head(5)
        for i, (_, post) in enumerate(top_posts.iterrows(), 1):
            with st.expander(f"#{i} {post['title']}"):
                st.markdown(f"""
                **r/{post['subreddit']}** • {post['score']} ⬆️ • {post['num_comments']} 💬
                
                [Read on Reddit]({post['permalink']})
                """)
    
    # Show raw data in an expander
    with st.expander("View Raw Data"):
        st.dataframe(df[['title', 'subreddit', 'score', 'num_comments', 'created_date']].sort_values('score', ascending=False))


def _time_window_to_days(time_window: str) -> int:
    """Convert time window string to days.
    
    Args:
        time_window: Time window string (e.g., '24h', '3d', '7d', '30d')
        
    Returns:
        Number of days as an integer
    """
    if time_window == '24h':
        return 1
    elif time_window == '3d':
        return 3
    elif time_window == '4d':
        return 4
    elif time_window == '5d':
        return 5
    elif time_window == '6d':
        return 6
    elif time_window == '7d':
        return 7
    elif time_window == '30d':
        return 30
    elif time_window == '60d':
        return 60
    elif time_window == '90d':
        return 90
    else:
        return 7  # Default to 7 days

def _get_reddit_client() -> Optional[RedditClient]:
    """Initialize and return RedditClient with credentials from environment."""
    try:
        return RedditClient()
    except Exception as e:
        logger.error(f"Failed to initialize Reddit client: {e}")
        st.error("Failed to initialize Reddit client. Please check your credentials in the .env file.")
        return None

def _search_reddit(query: str, subreddits: List[str], time_window: str, limit: int = 20) -> pd.DataFrame:
    """Search Reddit for posts matching the query and return a DataFrame.
    
    Args:
        query: The search query string
        subreddits: List of subreddits to search in (empty list means search all subreddits)
        time_window: Time window for search ('24h', '3d', '4d', '5d', '6d', '7d', '30d')
        limit: Maximum number of results to return
        
    Returns:
        DataFrame containing the search results
    """
    if not query or not query.strip():
        st.warning("Please enter a search query")
        return pd.DataFrame()
        
    # If subreddits is an empty list, it means search all subreddits
    search_all = not bool(subreddits)
    
    # Initialize the Reddit client
    reddit = _get_reddit_client()
    if not reddit:
        st.error("Failed to initialize Reddit client. Please check your credentials.")
        return pd.DataFrame()
    
    try:
        results = []
        
        # Convert time_window to days for date calculation
        days = 30  # default to 30 days if no match
        if time_window == '24h':
            days = 1
        elif time_window == '3d':
            days = 3
        elif time_window == '4d':
            days = 4
        elif time_window == '5d':
            days = 5
        elif time_window == '6d':
            days = 6
        elif time_window == '7d':
            days = 7
        
        # For custom date ranges (3d-8d), we'll need to filter results after fetching
        use_custom_date_filter = time_window in ['3d', '4d', '5d', '6d', '7d']
        
        # For Reddit's built-in filters, we can use their time_filter parameter
        time_filter = None
        if time_window == '24h':
            time_filter = 'day'
        elif time_window == '7d':
            time_filter = 'week'
        elif time_window == '30d':
            time_filter = 'month'
        else:
            # For custom date ranges, we'll fetch more results and filter after
            time_filter = 'month'  # Get a larger window to filter from
        
        # Search for posts
        try:
            if search_all:
                # Search all of Reddit by not specifying subreddits
                posts = reddit.search_posts(
                    query=query,
                    limit=limit,
                    sort="relevance",
                    time_filter=time_filter
                )
            else:
                # Search within specified subreddits
                posts = reddit.search_posts(
                    query=query,
                    subreddits=subreddits,
                    limit=limit,
                    sort="relevance",
                    time_filter=time_filter
                )
            
            # Process the posts
            if posts:
                current_time = datetime.utcnow()
                min_timestamp = (current_time - timedelta(days=days)).timestamp()
                
                for post in posts:
                    try:
                        # For custom date ranges, check if post is within the specified days
                        if use_custom_date_filter and post.created_utc < min_timestamp:
                            continue
                            
                        results.append({
                            'title': post.title,
                            'subreddit': post.subreddit,
                            'score': post.score,
                            'num_comments': post.num_comments,
                            'url': post.url,
                            'permalink': post.permalink,
                            'created_utc': post.created_utc,
                            'created_date': datetime.utcfromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                            'author': str(post.author) if post.author else '[deleted]',
                            'selftext': post.selftext
                        })
                    except Exception as e:
                        logger.warning(f"Error processing post: {e}")
                        continue
            
            # If no results from the initial search and not searching all subreddits, try getting top posts from each subreddit
            if not results and not search_all:
                for subreddit in subreddits:
                    try:
                        sub_posts = reddit.get_subreddit_posts(
                            subreddit=subreddit,
                            limit=min(limit, 5),  # Get fewer posts per subreddit
                            sort='top',
                            time_filter=time_filter
                        )
                        
                        for post in sub_posts:
                            try:
                                # Skip if we already have this post (by URL)
                                if any(r.get('url') == post.url for r in results):
                                    continue
                                    
                                results.append({
                                    'title': post.title,
                                    'subreddit': post.subreddit or subreddit,
                                    'score': post.score,
                                    'num_comments': post.num_comments,
                                    'url': post.url or f"https://www.reddit.com/r/{post.subreddit or subreddit}/comments/{post.id}",
                                    'created_utc': post.created_utc,
                                    'author': str(post.author) if post.author else '[deleted]',
                                    'selftext': post.selftext
                                })
                            except Exception as post_error:
                                logger.warning(f"Error processing post: {post_error}")
                                continue
                                
                    except Exception as subreddit_error:
                        logger.error(f"Error getting posts from r/{subreddit}: {subreddit_error}")
                        continue
            
            # Convert results to DataFrame and clean up
            if results:
                df = pd.DataFrame(results)
                
                # Add created_at datetime from timestamp if it exists
                if 'created_utc' in df.columns:
                    df['created_at'] = pd.to_datetime(df['created_utc'], unit='s')
                
                # Ensure all required columns exist
                for col in ['title', 'subreddit', 'score', 'num_comments', 'url', 'created_utc', 'author', 'selftext']:
                    if col not in df.columns:
                        df[col] = ''
                
                # Remove duplicates and sort
                df = df.drop_duplicates(subset=['url', 'title'])
                df = df.sort_values('score', ascending=False).head(limit)
                
                return df
                
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error in Reddit search: {e}", exc_info=True)
            st.error(f"An error occurred while searching Reddit: {str(e)}")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Unexpected error in _search_reddit: {e}", exc_info=True)
        st.error("An unexpected error occurred. Please try again later.")
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error in _search_reddit: {e}", exc_info=True)
        st.error(f"An error occurred while searching Reddit: {str(e)}")
        return pd.DataFrame()

def render_topic_explorer_tab(subreddits: List[str], time_window: str):
    """Render the Topic Explorer tab with search functionality and results visualization.
    
    Args:
        subreddits: List of subreddits to search in (empty list means search all subreddits)
        time_window: Time window for search ('24h', '7d', '30d')
    """
    st.subheader("🧭 Topic Explorer")
    
    # Display info about the current search scope
    search_scope = "All Subreddits" if not subreddits else f"r/{', r/'.join(subreddits)}"
    st.caption(f"🔍 Searching in: {search_scope} | ⏱️ Time window: {time_window}")
    
    # Search input with better styling
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input(
            "Search Reddit", 
            placeholder="e.g., AI regulation, climate policy",
            key="reddit_search_query",
            label_visibility="collapsed"
        )
    with col2:
        search_clicked = st.button("Search", use_container_width=True)
    
    # Add some space
    st.write("")
    
    # Handle search execution
    if (search_clicked or 'reddit_search_executed' in st.session_state) and search_query:
        if search_clicked:
            st.session_state.reddit_search_executed = True
            st.session_state.reddit_search_results = None
        
        with st.spinner(f"🔍 Searching for '{search_query}'..."):
            # Search Reddit for the query
            df = _search_reddit(
                query=search_query,
                subreddits=subreddits,
                time_window=time_window,
                limit=20  # Increased limit for better results
            )
            
            # Store results in session state to persist across reruns
            if search_clicked:
                st.session_state.reddit_search_results = df
            else:
                df = st.session_state.reddit_search_results
            
            if not df.empty:
                # Display results summary
                # Add export button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="💾 Export to CSV",
                    data=csv,
                    file_name=f"reddit_search_{'_'.join(subreddits) if subreddits else 'all'}_{time_window}.csv",
                    mime='text/csv',
                )
                
                st.success(f"✅ Found {len(df)} posts matching your query")
                
                # Show summary stats in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Posts", len(df))
                with col2:
                    avg_score = int(df['score'].mean()) if not df.empty else 0
                    st.metric("Avg. Score", f"{avg_score:,}")
                with col3:
                    total_comments = int(df['num_comments'].sum()) if not df.empty else 0
                    st.metric("Total Comments", f"{total_comments:,}")
                
                # Display posts in a nice card layout
                st.subheader("📰 Search Results")
                
                # Add sorting options
                sort_by = st.selectbox(
                    "Sort by",
                    ["Relevance", "Score (Highest First)", "Most Comments", "Newest First"],
                    index=0,
                    key="sort_results"
                )
                
                # Apply sorting
                if sort_by == "Score (Highest First)":
                    df = df.sort_values('score', ascending=False)
                elif sort_by == "Most Comments":
                    df = df.sort_values('num_comments', ascending=False)
                elif sort_by == "Newest First":
                    if 'created_utc' in df.columns:
                        df = df.sort_values('created_utc', ascending=False)
                
                # Display each post in a card
                for idx, row in df.iterrows():
                    with st.container():
                        # Create columns for the card
                        col1, col2 = st.columns([1, 10])
                        
                        # Left column for score and comments
                        with col1:
                            st.markdown(f"""
                                <div style='text-align: center;'>
                                    <div style='font-size: 1.2em; font-weight: bold;'>{row['score']:,}</div>
                                    <div style='font-size: 0.8em;'>points</div>
                                    <div style='margin: 10px 0;'>•</div>
                                    <div style='font-size: 1.2em; font-weight: bold;'>{row['num_comments']:,}</div>
                                    <div style='font-size: 0.8em;'>comments</div>
                                </div>
                            """, unsafe_allow_html=True)
                        
                        # Right column for post content
                        with col2:
                            # Post title and metadata
                            st.markdown(f"### {row['title']}")
                            st.caption(
                                f"Posted in r/{row['subreddit']} by u/{row['author']} • "
                                f"{row['created_utc'] if 'created_utc' in row else 'Unknown date'}"
                            )
                            
                            # Truncate and show post content with expander
                            if 'selftext' in row and row['selftext']:
                                with st.expander("View post content"):
                                    st.markdown(row['selftext'][:500] + ('' if len(row['selftext']) <= 500 else '...'))
                            
                            # Action buttons
                            btn1, btn2 = st.columns([1, 5])
                            with btn1:
                                st.link_button("🔗 View on Reddit", row['url'])
                            with btn2:
                                if st.button("📋 Copy Link", key=f"copy_{idx}"):
                                    st.session_state[f"copied_{idx}"] = True
                                    st.rerun()
                                if st.session_state.get(f"copied_{idx}", False):
                                    st.success("Link copied!")
                            
                            st.divider()
                
                # Show analytics section
                st.subheader("📊 Analysis")
                
                # Create tabs for different visualizations
                tab1, tab2, tab3 = st.tabs(["Subreddit Distribution", "Score Analysis", "Engagement"]) 
                
                with tab1:
                    # Subreddit distribution pie chart
                    if 'subreddit' in df.columns and not df.empty:
                        subreddit_counts = df['subreddit'].value_counts().reset_index()
                        subreddit_counts.columns = ['Subreddit', 'Count']
                        
                        if not subreddit_counts.empty:
                            fig = px.pie(
                                subreddit_counts, 
                                names='Subreddit', 
                                values='Count',
                                title=f'Posts by Subreddit for "{search_query}"',
                                hole=0.4
                            )
                            st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    # Score distribution
                    if 'score' in df.columns and not df.empty:
                        fig = px.histogram(
                            df, 
                            x='score',
                            title='Distribution of Post Scores',
                            labels={'score': 'Post Score'},
                            color_discrete_sequence=['#FF4B4B']
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                with tab3:
                    # Engagement (score vs comments)
                    if not df.empty and 'score' in df.columns and 'num_comments' in df.columns:
                        fig = px.scatter(
                            df, 
                            x='score', 
                            y='num_comments',
                            color='subreddit',
                            hover_data=['title'],
                            title='Engagement: Score vs Number of Comments',
                            labels={'score': 'Score', 'num_comments': 'Number of Comments'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Export options
                st.download_button(
                    label="📥 Export Results (CSV)",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name=f"reddit_search_{search_query[:20]}.csv",
                    mime='text/csv',
                    use_container_width=True
                )
                
            else:
                st.warning("❌ No posts found matching your search criteria. Try a different query or check the subreddits you're searching in.")
                
                # Show suggestions for better searches
                st.info("💡 Tips for better searches:")
                st.markdown("""
                - Try different keywords or phrases
                - Be more specific with your search terms
                - Check if the subreddits you're searching in are active
                - Try a broader time window
                """)
    
    # Initial state - show help and examples
    else:
        # Show search tips
        with st.expander("ℹ️ How to use the Topic Explorer", expanded=True):
            st.markdown("""
            ### Find trending discussions on Reddit
            
            1. **Enter a search term** in the box above
            2. **Click Search** to find relevant posts
            3. **Analyze** the results with interactive charts
            4. **Filter and sort** to find what you're looking for
            
            ### Tips for better searches:
            - Use quotes for exact phrases: `"machine learning"`
            - Exclude terms with minus: `python -snake`
            - Search specific subreddits: `subreddit:python pandas`
            - Find recent posts: sort by "Newest First"
            - Look for highly engaged content: sort by "Most Comments"
            """)
        
        # Show example searches
        st.write("## 🔍 Example Searches")
        st.write("Try searching for:")
        
        # Define the search examples
        examples = [
            "best programming laptop 2024",
            "AI art generators comparison",
            "remote work productivity tips",
            "sustainable energy news",
            "machine learning projects for beginners"
        ]
        
        # Display example search queries as non-clickable buttons
        for i, query in enumerate(examples):
            st.markdown(f"""
            <div style="margin: 0.5rem 0; padding: 0.5rem 1rem; 
                        border: 1px solid #e0e0e0; border-radius: 0.5rem;">
                {query}
            </div>
            """, unsafe_allow_html=True)
        
        # Create the search input
        search_query = st.text_input(
            "Search Reddit", 
            placeholder="e.g., AI regulation, climate policy",
            key="reddit_search_input"
        )
        
        # Add the search button
        search_clicked = st.button("Search", use_container_width=True, type="primary")


def _create_gauge_chart(score: float, title: str):
    """Create a gauge chart for the virality score."""
    import plotly.graph_objects as go
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 40], 'color': 'lightcoral'},
                {'range': [40, 70], 'color': 'lightyellow'},
                {'range': [70, 90], 'color': 'lightgreen'},
                {'range': [90, 100], 'color': 'lime'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(l=30, r=30, t=50, b=10),
        font=dict(color="black", size=14)
    )
    
    return fig

def _create_sentiment_gauge(score: float):
    """Create a sentiment gauge chart."""
    import plotly.graph_objects as go
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score * 100,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Sentiment"},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 30], 'color': 'lightcoral'},
                {'range': [30, 40], 'color': 'lightpink'},
                {'range': [40, 60], 'color': 'lightyellow'},
                {'range': [60, 70], 'color': 'lightgreen'},
                {'range': [70, 100], 'color': 'lime'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': score * 100
            }
        }
    ))
    
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=50, b=10),
        font=dict(color="black", size=12)
    )
    
    return fig

def render_virality_scorer_tab(subreddits: List[str], time_window: str):
    st.subheader("🚀 Virality Scorer")
    st.caption("Analyze your headline's potential to go viral on Reddit based on current trends")
    
    # Add some space
    st.write("")
    
    with st.form("headline_form"):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            headline = st.text_area(
                "Enter your headline",
                placeholder="Type your headline here...",
                height=100,
                help="Enter a headline to analyze its virality potential against current trends"
            )
        
        with col2:
            st.write("")
            st.write("")
            submit = st.form_submit_button("🔍 Analyze Headline", use_container_width=True)
    
    if submit and headline.strip():
        # Show loading state
        with st.spinner('Analyzing your headline against current trends...'):
            # Analyze the headline with trend analysis
            analysis = _analyze_headline_virality(headline, subreddits, time_window)
            
            # Main score display
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                st.plotly_chart(
                    _create_gauge_chart(analysis['score'], "Virality Score"), 
                    use_container_width=True
                )
            
            with col2:
                st.plotly_chart(
                    _create_sentiment_gauge(analysis['metrics']['sentiment']),
                    use_container_width=True
                )
            
            with col3:
                st.metric("Trend Relevance", f"{analysis['metrics']['trend_score']*100:.0f}%")
                st.metric("Engagement Potential", f"{analysis['metrics']['sentiment_magnitude']*100:.0f}%")
                st.metric("Word Count", 
                        f"{analysis['metrics']['word_count']} words",
                        "Optimal: 8-12 words" if 8 <= analysis['metrics']['word_count'] <= 12 
                        else "Too short" if analysis['metrics']['word_count'] < 8 
                        else "Too long"
                )
            
            # Trend Matches Section
            if analysis['metrics']['trend_matches']:
                with st.expander("📈 Trend Matches", expanded=True):
                    st.subheader("Trending Topics in Your Headline")
                    trend_df = pd.DataFrame(
                        analysis['metrics']['trend_matches'],
                        columns=["Trending Term", "Relevance"]
                    )
                    trend_df['Relevance'] = (trend_df['Relevance'] * 100).round(1).astype(str) + '%'
                    st.dataframe(
                        trend_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Trending Term": "Trending Term",
                            "Relevance": st.column_config.ProgressColumn(
                                "Relevance",
                                help="How relevant this term is to current trends",
                                format="%s",
                                min_value=0,
                                max_value=100,
                            )
                        }
                    )
            
            # Detailed metrics
            with st.expander("📊 Detailed Analysis", expanded=True):
                st.subheader("Key Metrics")
                
                # Create metrics in a grid
                metrics_cols = st.columns(4)
                with metrics_cols[0]:
                    st.metric("Trend Relevance", f"{analysis['metrics']['trend_score']*100:.0f}/100")
                with metrics_cols[1]:
                    st.metric("Sentiment", 
                            "😊" if analysis['metrics']['sentiment'] > 0.6 
                            else "😐" if analysis['metrics']['sentiment'] > 0.4 
                            else "😟")
                with metrics_cols[2]:
                    st.metric("Engagement", f"{analysis['metrics']['sentiment_magnitude']*100:.0f}%")
                with metrics_cols[3]:
                    st.metric("Length", 
                            f"{analysis['metrics']['word_count']} words",
                            "Optimal" if 8 <= analysis['metrics']['word_count'] <= 12 
                            else "Too short" if analysis['metrics']['word_count'] < 8 
                            else "Too long"
                    )
                
                # Show features in a table
                st.subheader("Score Breakdown")
                st.dataframe(
                    pd.DataFrame(analysis['features']),
                    use_container_width=True,
                    hide_index=True
                )
            
            # Suggestions for improvement
            with st.expander("💡 Suggestions to Improve", expanded=True):
                if not analysis['suggestions']:
                    st.success("🎉 Great headline! It has good potential for virality.")
                else:
                    for tip in analysis['suggestions']:
                        st.write(f"• {tip}")
                
                st.write("")
                st.markdown("### Pro Tips for High-Virality Headlines")
                st.markdown("""
                - **Leverage trends**: Include currently popular topics from your target subreddits
                - **Use numbers**: "5 Ways to..." or "10 Tips for..."
                - **Ask questions**: Engage readers with thought-provoking questions
                - **Be specific**: Vague headlines get less engagement
                - **Optimal length**: 8-12 words work best for engagement
                - **Test variations**: Try different phrasings to see what resonates
                """)
            
            # Trend Analysis Section
            with st.expander("🔍 Trend Analysis", expanded=False):
                st.write("Analyzing current trends in your target subreddits...")
                
                # Get trending keywords for the selected subreddits
                trending_keywords = _get_trending_keywords(subreddits, time_window, limit=15)
                
                if trending_keywords:
                    # Create a bar chart of top trending terms
                    trend_df = pd.DataFrame(
                        trending_keywords.items(), 
                        columns=['Term', 'Trend Score']
                    ).sort_values('Trend Score', ascending=False)
                    
                    st.markdown("### Top Trending Terms")
                    st.bar_chart(
                        trend_df.set_index('Term'),
                        use_container_width=True
                    )
                    
                    # Show the full list of trending terms
                    st.markdown("### All Trending Terms")
                    trend_df['Trend Score'] = (trend_df['Trend Score'] * 100).round(1).astype(str) + '%'
                    st.dataframe(
                        trend_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Term": "Trending Term",
                            "Trend Score": st.column_config.ProgressColumn(
                                "Trend Score",
                                help="How popular this term is in your target subreddits",
                                format="%s",
                                min_value=0,
                                max_value=100,
                            )
                        }
                    )
                else:
                    st.warning("Could not fetch trending data. Please check your Reddit API credentials and try again.")
    
    elif submit and not headline.strip():
        st.warning("Please enter a headline to analyze.")
    else:
        # Show placeholder/instructions
        st.info("💡 Enter a headline above to analyze its virality potential against current trends. "
               "The analyzer will compare your headline with what's currently popular in your selected subreddits.")
        
        # Example headlines
        st.markdown("### Example Headlines to Try")
        examples = [
            "5 Simple Habits That Will Transform Your Morning Routine",
            "The Shocking Truth About Productivity in 2023",
            "How I Grew My Business by 300% in Just 6 Months",
            "10 Must-Have Tools for Remote Workers in 2023",
            "The Science of Happiness: What Research Tells Us"
        ]
        
        for example in examples:
            if st.button(example, key=f"example_{example}"):
                st.session_state.headline = example
                st.experimental_rerun()
