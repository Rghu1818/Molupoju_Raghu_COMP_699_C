from typing import List, Dict, Any, Optional, Union, Tuple
import logging
import time
from dataclasses import dataclass
import requests
from urllib.parse import urljoin
import re
from datetime import datetime, timedelta
import random

@dataclass
class RedditPost:
    """Dataclass representing a Reddit post."""
    id: str
    title: str
    selftext: str
    score: int
    subreddit: str
    url: str
    permalink: str
    created_utc: float
    num_comments: int
    author: str
    is_self: bool = False
    
    def __post_init__(self):
        # Clean up string fields
        self.title = str(self.title).strip() if self.title else ""
        self.selftext = str(self.selftext).strip() if self.selftext else ""
        self.subreddit = str(self.subreddit).lower().replace('r/', '') if self.subreddit else ""
        self.author = str(self.author) if self.author else ""
        
        # Ensure numeric fields are the correct type
        self.score = int(self.score) if self.score is not None else 0
        self.num_comments = int(self.num_comments) if self.num_comments is not None else 0
        self.created_utc = float(self.created_utc) if self.created_utc is not None else 0
        
        # Ensure URLs are properly formatted
        if self.permalink and not self.permalink.startswith('http'):
            self.permalink = urljoin("https://www.reddit.com", self.permalink)
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert the post to a dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'selftext': self.selftext,
            'score': self.score,
            'subreddit': self.subreddit,
            'url': self.url,
            'permalink': self.permalink,
            'created_utc': self.created_utc,
            'num_comments': self.num_comments,
            'author': self.author,
            'is_self': self.is_self
        }

@dataclass
class RedditComment:
    """Dataclass representing a Reddit comment."""
    id: str
    body: str
    score: int
    author: str
    created_utc: float
    parent_id: str
    is_submitter: bool = False
    
    def __post_init__(self):
        # Clean up string fields
        self.body = str(self.body).strip() if self.body else ""
        self.author = str(self.author) if self.author else ""
        self.parent_id = str(self.parent_id) if self.parent_id else ""
        
        # Ensure numeric fields are the correct type
        self.score = int(self.score) if self.score is not None else 0
        self.created_utc = float(self.created_utc) if self.created_utc is not None else 0
        self.is_submitter = bool(self.is_submitter)

# Configure logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RateLimitExceededError(Exception):
    """Exception raised when the rate limit is exceeded."""
    def __init__(self, retry_after: int = 60, message="Rate limit exceeded"):
        self.retry_after = retry_after
        self.message = f"{message}. Please try again in {retry_after} seconds."
        super().__init__(self.message)

class RedditScraper:
    """A class to scrape data from Reddit using the RapidAPI Reddit34 API."""
    
    BASE_URL = "https://reddit34.p.rapidapi.com"
    REDDIT_BASE_URL = "https://www.reddit.com"
    
    # Endpoints
    ENDPOINT_SEARCH = "search"
    ENDPOINT_SUBREDDIT = "r/{subreddit}/{sort}"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 5  # Number of requests per window
    RATE_LIMIT_WINDOW = 60   # Time window in seconds
    _last_request_time = 0
    _request_count = 0
    _rate_limit_reset = 0
    
    def __init__(self, api_key: str):
        """Initialize the RedditScraper with API credentials.
        
        Args:
            api_key: Your RapidAPI key
        """
        self.headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "reddit34.p.rapidapi.com"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _handle_rate_limit(self):
        """Handle rate limiting by sleeping if needed."""
        current_time = time.time()
        
        # Reset counter if window has passed
        if current_time - self._last_request_time > self.RATE_LIMIT_WINDOW:
            self._request_count = 0
            self._last_request_time = current_time
        
        # If we've hit the rate limit, sleep until the window resets
        if self._request_count >= self.RATE_LIMIT_REQUESTS:
            sleep_time = (self._last_request_time + self.RATE_LIMIT_WINDOW) - current_time + 1
            if sleep_time > 0:
                logger.warning(f"Rate limit reached. Sleeping for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                self._request_count = 0
                self._last_request_time = time.time()
        
        # Add a small jitter to avoid thundering herd
        time.sleep(random.uniform(0.1, 0.5))
    
    def _make_request(self, endpoint: str, params: Dict[str, Any], max_retries: int = 3) -> Tuple[Optional[Dict], Optional[Exception]]:
        """Make a request to the Reddit API with rate limiting and retries.
        
        Args:
            endpoint: API endpoint to call
            params: Query parameters for the request
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (response_data, error)
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                # Check and handle rate limiting
                self._handle_rate_limit()
                
                # Make the request
                url = f"{self.BASE_URL}/{endpoint}"
                logger.info(f"Making request to {url} with params: {params}")
                
                start_time = time.time()
                response = self.session.get(
                    url,
                    params=params,
                    timeout=15,
                    headers={
                        **self.session.headers,
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                )
                
                # Log request duration
                duration = time.time() - start_time
                logger.debug(f"Request completed in {duration:.2f}s")
                
                # Handle rate limiting (429 status code)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                    time.sleep(retry_after + random.uniform(0.5, 2.0))  # Add some jitter
                    retry_count += 1
                    continue
                    
                response.raise_for_status()
                
                data = response.json()
                logger.debug(f"API response: {data}")
                
                # Handle different response formats
                if 'data' in data:
                    return data, None
                elif 'posts' in data:  # Some endpoints return posts directly
                    return {'data': data['posts']}, None
                elif isinstance(data, list):  # Some endpoints return an array
                    return {'data': data}, None
                else:
                    logger.warning(f"Unexpected API response format: {data}")
                    return {'data': []}, None
                
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
                
                if status_code == 429:  # Rate limited
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    logger.error(f"Rate limit exceeded. Retry after {retry_after} seconds.")
                    if retry_count < max_retries:
                        time.sleep(retry_after + random.uniform(1, 3))  # Add some jitter
                        retry_count += 1
                        continue
                    else:
                        raise RateLimitExceededError(retry_after=retry_after)
                
                logger.error(f"HTTP Error {status_code}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_data = e.response.json()
                        logger.error(f"API error response: {error_data}")
                    except:
                        error_text = e.response.text[:500]  # Limit error text length
                        logger.error(f"API error response (non-JSON): {error_text}")
                
                if retry_count < max_retries:
                    retry_delay = (2 ** retry_count) + random.random()  # Exponential backoff with jitter
                    logger.warning(f"Retrying in {retry_delay:.1f} seconds... (attempt {retry_count + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_count += 1
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded for request to {endpoint}")
                    return None, e
                    
            except (requests.exceptions.RequestException, ValueError) as e:
                last_error = e
                logger.error(f"Request failed: {e}")
                if retry_count < max_retries:
                    retry_delay = (2 ** retry_count) + random.random()
                    logger.warning(f"Retrying in {retry_delay:.1f} seconds... (attempt {retry_count + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_count += 1
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded for request to {endpoint}")
                    return None, e
                    
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in _make_request: {e}", exc_info=True)
                if retry_count < max_retries:
                    retry_delay = (2 ** retry_count) + random.random()
                    logger.warning(f"Retrying in {retry_delay:.1f} seconds... (attempt {retry_count + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_count += 1
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded for request to {endpoint}")
                    return None, e
        
        return None, last_error or Exception("Unknown error occurred")
    
    def search_posts(self, query: str, subreddit: str = None, limit: int = 10, 
                    sort: str = "relevance", time_filter: str = "all") -> List[RedditPost]:
        """Search for Reddit posts matching a query.
        
        Args:
            query: Search query string
            subreddit: Optional subreddit to search within
            limit: Maximum number of posts to return (max 100)
            sort: How to sort results (relevance, hot, top, new, comments)
            time_filter: Time period to search (all, day, hour, month, week, year)
            
        Returns:
            List of RedditPost objects
        """
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return []
            
        params = {
            "query": query.strip(),
            "limit": min(100, max(1, limit)),
            "sort": sort,
            "time": time_filter
        }
        
        if subreddit and str(subreddit).strip():
            params["subreddit"] = str(subreddit).strip()
        
        try:
            data, error = self._make_request(self.ENDPOINT_SEARCH, params)
            
            if error:
                if isinstance(error, RateLimitExceededError):
                    raise error
                logger.error(f"Error in search_posts: {error}")
                return []
                
            if not data or 'data' not in data:
                logger.warning("No post data found in search response")
                return []
                
            posts = []
            for post_data in data['data']:
                try:
                    # Skip if missing required fields
                    if not post_data.get('id') or not post_data.get('title'):
                        continue
                        
                    # Handle potentially missing fields
                    permalink = post_data.get('permalink', '')
                    if permalink and not permalink.startswith('http'):
                        permalink = urljoin(self.REDDIT_BASE_URL, permalink)
                    
                    # Get subreddit name, handling different API responses
                    post_subreddit = post_data.get('subreddit', subreddit or '')
                    if post_subreddit:
                        post_subreddit = str(post_subreddit).lower().replace('r/', '')
                    
                    post = RedditPost(
                        id=post_data.get('id', ''),
                        title=post_data.get('title', '').strip(),
                        selftext=post_data.get('selftext', post_data.get('body', '')),
                        score=int(post_data.get('score', post_data.get('ups', 0))),
                        subreddit=post_subreddit,
                        url=post_data.get('url', ''),
                        permalink=permalink,
                        created_utc=post_data.get('created_utc', 0),
                        num_comments=int(post_data.get('num_comments', 0)),
                        author=post_data.get('author', ''),
                        is_self=post_data.get('is_self', False)
                    )
                    posts.append(post)
                except Exception as e:
                    logger.error(f"Error parsing post: {e}")
                    logger.debug(f"Problematic post data: {post_data}")
                    continue
                    
            return posts
            
        except RateLimitExceededError as e:
            logger.error(f"Rate limit exceeded in search_posts: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in search_posts: {e}", exc_info=True)
            return []
    
    def get_subreddit_posts(self, subreddit: str, limit: int = 10, 
                          sort: str = "hot", time_filter: str = "day") -> List[RedditPost]:
        """Get posts from a specific subreddit.
        
        Args:
            subreddit: Name of the subreddit (without r/)
            limit: Maximum number of posts to return (max 100)
            sort: How to sort posts (hot, new, top, rising)
            time_filter: Time period for top posts (hour, day, week, month, year, all)
            
        Returns:
            List of RedditPost objects
        """
        if not subreddit or not str(subreddit).strip():
            logger.warning("No subreddit specified")
            return []
            
        subreddit = str(subreddit).strip().lower().replace('r/', '')
        endpoint = self.ENDPOINT_SUBREDDIT.format(
            subreddit=subreddit, 
            sort=sort.lower()
        )
        
        params = {
            "limit": min(100, max(1, limit)),
            "time": time_filter if sort.lower() == "top" else "day"
        }
        
        try:
            data, error = self._make_request(endpoint, params)
            
            if error:
                if isinstance(error, RateLimitExceededError):
                    raise error
                logger.error(f"Error in get_subreddit_posts: {error}")
                return []
                
            if not data or 'data' not in data:
                logger.warning(f"No posts found for subreddit: r/{subreddit}")
                return []
                
            posts = []
            for post_data in data['data']:
                try:
                    # Skip if missing required fields
                    if not post_data.get('id') or not post_data.get('title'):
                        continue
                        
                    # Handle potentially missing fields
                    permalink = post_data.get('permalink', '')
                    if permalink and not permalink.startswith('http'):
                        permalink = urljoin(self.REDDIT_BASE_URL, permalink)
                        
                    # Get subreddit name, handling different API responses
                    post_subreddit = post_data.get('subreddit', subreddit)
                    if post_subreddit:
                        post_subreddit = str(post_subreddit).lower().replace('r/', '')
                    
                    post = RedditPost(
                        id=post_data.get('id', ''),
                        title=post_data.get('title', '').strip(),
                        selftext=post_data.get('selftext', post_data.get('body', '')),
                        score=int(post_data.get('score', post_data.get('ups', 0))),
                        subreddit=post_subreddit,
                        url=post_data.get('url', ''),
                        permalink=permalink,
                        created_utc=post_data.get('created_utc', 0),
                        num_comments=int(post_data.get('num_comments', 0)),
                        author=post_data.get('author', ''),
                        is_self=post_data.get('is_self', False)
                    )
                    posts.append(post)
                except Exception as e:
                    logger.error(f"Error parsing post: {e}")
                    logger.debug(f"Problematic post data: {post_data}")
                    continue
                    
            return posts
            
        except RateLimitExceededError as e:
            logger.error(f"Rate limit exceeded in get_subreddit_posts: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_subreddit_posts: {e}", exc_info=True)
            return []
    
    def get_post_comments(self, post_url: str, sort: str = "top", limit: int = 10) -> List[RedditComment]:
        """Fetch comments from a Reddit post.
        
        Args:
            post_url: URL of the Reddit post
            sort: How to sort comments (top, new, best, controversial, old, q&a)
            limit: Maximum number of comments to return (max 100)
            
        Returns:
            List of RedditComment objects
        """
        # Extract subreddit and post ID from URL if it's a full URL
        subreddit = None
        post_id = None
        
        if "reddit.com" in post_url:
            # Parse the URL to get subreddit and post ID
            import re
            match = re.search(r'reddit\.com/r/([^/]+)/comments/([^/]+)', post_url)
            if match:
                subreddit = match.group(1)
                post_id = match.group(2)
        
        params = {
            "url": post_url,
            "sort": sort,
            "limit": min(100, max(1, limit))
        }
        
        data = self._make_request("getPostCommentsWithSort", params)
        if not data or 'data' not in data:
            logger.warning("No comment data found in response")
            return []
            
        comments = []
        for comment_data in data['data']:
            try:
                comment = RedditComment(
                    id=comment_data.get('id', ''),
                    author=comment_data.get('author', ''),
                    body=comment_data.get('body', ''),
                    score=comment_data.get('score', 0),
                    created_utc=comment_data.get('created_utc', 0),
                    permalink=urljoin(self.REDDIT_BASE_URL, comment_data.get('permalink', '')),
                    is_submitter=comment_data.get('is_submitter', False),
                    parent_id=comment_data.get('parent_id', ''),
                    subreddit=subreddit or '',
                    post_id=post_id or ''
                )
                comments.append(comment)
            except Exception as e:
                logger.error(f"Error parsing comment: {e}")
        
        return comments
    
    def search_and_analyze(self, query: str, subreddits: List[str] = None, 
                          post_limit: int = 5, comment_limit: int = 10,
                          sort_posts: str = "relevance", sort_comments: str = "top") -> List[Dict[str, Any]]:
        """Search for posts and fetch their comments for analysis.
        
        Args:
            query: Search query string
            subreddits: Optional list of subreddits to search in
            post_limit: Maximum number of posts to return per subreddit
            comment_limit: Maximum number of comments to fetch per post
            sort_posts: How to sort posts (relevance, hot, top, new, comments)
            sort_comments: How to sort comments (top, new, best, controversial, old, q&a)
            
        Returns:
            List of dictionaries containing post and comment data
        """
        results = []
        
        if subreddits:
            # Search in specific subreddits
            for subreddit in subreddits:
                logger.info(f"Searching in r/{subreddit} for: {query}")
                posts = self.search_posts(
                    query=query,
                    subreddit=subreddit,
                    limit=post_limit,
                    sort=sort_posts
                )
                
                for post in posts:
                    post_data = self._process_post(post, comment_limit, sort_comments)
                    results.append(post_data)
                    # Be nice to the API
                    time.sleep(1)
        else:
            # Global search
            logger.info(f"Performing global search for: {query}")
            posts = self.search_posts(
                query=query,
                limit=post_limit * (len(subreddits) if subreddits else 1),
                sort=sort_posts
            )
            
            for post in posts:
                post_data = self._process_post(post, comment_limit, sort_comments)
                results.append(post_data)
                # Be nice to the API
                time.sleep(1)
        
        return results
    
    def _process_post(self, post: RedditPost, comment_limit: int, sort: str) -> Dict[str, Any]:
        """Process a single post and fetch its comments."""
        logger.info(f"Processing post: {post.title}")
        
        # Get comments for the post
        comments = self.get_post_comments(
            post_url=post.permalink,
            sort=sort,
            limit=comment_limit
        )
        
        # Convert comments to dicts
        comments_data = [{
            'id': c.id,
            'author': c.author,
            'body': c.body,
            'score': c.score,
            'created_utc': c.created_utc,
            'permalink': c.permalink,
            'is_submitter': c.is_submitter,
            'parent_id': c.parent_id
        } for c in comments]
        
        # Return post data with comments
        return {
            'post': {
                'id': post.id,
                'title': post.title,
                'selftext': post.selftext,
                'score': post.score,
                'subreddit': post.subreddit,
                'url': post.url,
                'permalink': post.permalink,
                'created_utc': post.created_utc,
                'num_comments': post.num_comments,
                'author': post.author
            },
            'comments': comments_data
        }
