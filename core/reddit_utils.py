import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import time

def search_reddit_posts(query: str, sort: str = "relevance", time_filter: str = "month", limit: int = 10) -> Optional[Dict]:
    """
    Search Reddit for posts matching a query.
    
    Args:
        query: Search query string
        sort: How to sort results (relevance, hot, top, new, comments)
        time_filter: Time period to search (hour, day, week, month, year, all)
        limit: Maximum number of posts to return (1-100)
        
    Returns:
        Dictionary containing search results or None if request fails
    """
    url = "https://reddit34.p.rapidapi.com/search"
    
    headers = {
        "x-rapidapi-key": "decb520213msh7a1e8b6e0ccee21p100c9ejsn32179def5fad",
        "x-rapidapi-host": "reddit34.p.rapidapi.com"
    }
    
    params = {
        "query": query,
        "sort": sort,
        "time": time_filter,
        "limit": min(max(1, limit), 100)  # Ensure limit is between 1 and 100
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error searching Reddit: {e}")
        return None

def get_post_comments(post_id: str, subreddit: str, limit: int = 100, sort: str = "top") -> Optional[Dict]:
    """
    Get comments from a specific Reddit post.
    
    Args:
        post_id: The post ID (without the 't3_' prefix)
        subreddit: The subreddit name (without 'r/')
        limit: Maximum number of comments to return (1-500)
        sort: How to sort comments (confidence, top, new, controversial, old, random, q&a)
        
    Returns:
        Dictionary containing comments or None if request fails
    """
    url = f"https://reddit34.p.rapidapi.com/comments/{post_id}"
    
    headers = {
        "x-rapidapi-key": "decb520213msh7a1e8b6e0ccee21p100c9ejsn32179def5fad",
        "x-rapidapi-host": "reddit34.p.rapidapi.com"
    }
    
    params = {
        "subreddit": subreddit,
        "limit": min(max(1, limit), 500),  # Ensure limit is between 1 and 500
        "sort": sort
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Reddit comments: {e}")
        return None

def process_reddit_posts(posts_data: Dict) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Process Reddit posts data into a pandas DataFrame.
    
    Args:
        posts_data: Raw posts data from Reddit API search
        
    Returns:
        Tuple of (DataFrame containing processed posts, List of post metadata)
    """
    if not posts_data or 'data' not in posts_data or 'children' not in posts_data['data']:
        return pd.DataFrame(), []
    
    posts = []
    post_metadata = []
    
    for post in posts_data['data']['children']:
        if not isinstance(post, dict) or 'data' not in post:
            continue
            
        post_data = post['data']
        
        # Extract basic post information
        post_metadata.append({
            'id': post_data.get('id'),
            'title': post_data.get('title', ''),
            'subreddit': post_data.get('subreddit', ''),
            'author': post_data.get('author', ''),
            'score': post_data.get('score', 0),
            'num_comments': post_data.get('num_comments', 0),
            'created_utc': post_data.get('created_utc'),
            'url': f"https://www.reddit.com{post_data.get('permalink', '')}",
            'selftext': post_data.get('selftext', '')
        })
        
        # Add post as a comment
        posts.append({
            'id': post_data.get('id'),
            'post_id': post_data.get('id'),
            'author': post_data.get('author', ''),
            'body': f"{post_data.get('title', '')}\n\n{post_data.get('selftext', '')}",
            'score': post_data.get('score', 0),
            'created_utc': post_data.get('created_utc'),
            'depth': 0,  # Post is at depth 0
            'is_submitter': True,
            'is_post': True,
            'permalink': f"https://www.reddit.com{post_data.get('permalink', '')}",
            'subreddit': post_data.get('subreddit', '')
        })
    
    return pd.DataFrame(posts), post_metadata

def process_reddit_comments(comments_data: Dict, post_id: str, subreddit: str) -> pd.DataFrame:
    """
    Process Reddit comments data into a pandas DataFrame.
    
    Args:
        comments_data: Raw comments data from Reddit API
        post_id: The ID of the post these comments belong to
        subreddit: The subreddit name
        
    Returns:
        DataFrame containing processed comments
    """
    if not comments_data or 'data' not in comments_data or not comments_data['data']:
        return pd.DataFrame()
    
    comments = []
    
    def extract_comments(comment_list, depth=0, parent_id=None):
        for comment in comment_list:
            if not isinstance(comment, dict) or 'kind' not in comment or comment['kind'] != 't1':
                continue
                
            comment_data = comment.get('data', {})
            
            if 'body' in comment_data and comment_data['body']:
                comment_dict = {
                    'id': comment_data.get('id'),
                    'post_id': post_id,
                    'parent_id': parent_id,
                    'author': comment_data.get('author', ''),
                    'body': comment_data.get('body', ''),
                    'score': comment_data.get('score', 0),
                    'created_utc': comment_data.get('created_utc'),
                    'depth': depth,
                    'is_submitter': comment_data.get('is_submitter', False),
                    'is_post': False,
                    'permalink': f"https://www.reddit.com{comment_data.get('permalink', '')}",
                    'subreddit': subreddit
                }
                comments.append(comment_dict)
            
            # Recursively process replies
            if 'replies' in comment_data and comment_data['replies'] and isinstance(comment_data['replies'], dict):
                extract_comments(
                    comment_data['replies'].get('data', {}).get('children', []), 
                    depth + 1, 
                    parent_id=comment_data.get('id')
                )
    
    # Start processing top-level comments
    for comment in comments_data['data'].get('children', []):
        extract_comments([comment], depth=0, parent_id=post_id)
    
    # Convert to DataFrame
    df = pd.DataFrame(comments)
    
    # Convert timestamp if it exists
    if 'created_utc' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_utc'], unit='s')
    
    return df

def get_reddit_topic_data(topic: str, time_filter: str = "month", max_posts: int = 5, max_comments_per_post: int = 50) -> Tuple[pd.DataFrame, Dict]:
    """
    Get Reddit data for a specific topic.
    
    Args:
        topic: The topic to search for
        time_filter: Time period to search (hour, day, week, month, year, all)
        max_posts: Maximum number of posts to fetch
        max_comments_per_post: Maximum number of comments to fetch per post
        
    Returns:
        Tuple of (DataFrame containing posts and comments, metadata dictionary)
    """
    print(f"Searching Reddit for topic: {topic}")
    
    # Search for posts about the topic
    search_results = search_reddit_posts(
        query=topic,
        time_filter=time_filter,
        limit=max_posts
    )
    
    if not search_results:
        return pd.DataFrame(), {'error': 'No results found'}
    
    # Process the search results
    posts_df, post_metadata = process_reddit_posts(search_results)
    
    if posts_df.empty:
        return pd.DataFrame(), {'error': 'No valid posts found'}
    
    all_comments = []
    
    # Get comments for each post
    for post in post_metadata:
        post_id = post['id']
        subreddit = post['subreddit']
        
        print(f"Fetching comments for post: {post_id} in r/{subreddit}")
        
        # Get comments for this post
        comments_data = get_post_comments(
            post_id=post_id,
            subreddit=subreddit,
            limit=max_comments_per_post
        )
        
        if comments_data and 'data' in comments_data and len(comments_data['data']) > 1:
            # The first item is the post itself, which we already have
            comments_df = process_reddit_comments(
                comments_data=comments_data[1],  # Comments are in the second item
                post_id=post_id,
                subreddit=subreddit
            )
            
            if not comments_df.empty:
                all_comments.append(comments_df)
    
    # Combine all comments into a single DataFrame
    combined_comments = pd.concat(all_comments, ignore_index=True) if all_comments else pd.DataFrame()
    
    # Combine posts and comments
    if not combined_comments.empty:
        result_df = pd.concat([posts_df, combined_comments], ignore_index=True)
    else:
        result_df = posts_df
    
    # Prepare metadata
    metadata = {
        'topic': topic,
        'time_filter': time_filter,
        'num_posts': len(post_metadata),
        'num_comments': len(combined_comments),
        'subreddits': list(set(post['subreddit'] for post in post_metadata if post.get('subreddit'))),
        'posts': post_metadata
    }
    
    return result_df, metadata
