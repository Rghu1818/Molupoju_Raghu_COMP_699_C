import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import praw
from dotenv import load_dotenv
from dataclasses import dataclass

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

class RedditClient:
    """A client for interacting with the Reddit API using PRAW."""
    
    def __init__(self):
        """Initialize the Reddit client with credentials from environment variables."""
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'v_trends/0.1 by TomorrowCharacter519')
        self.username = os.getenv('REDDIT_USERNAME')
        self.password = os.getenv('REDDIT_PASSWORD')
        
        if not all([self.client_id, self.client_secret, self.username, self.password]):
            raise ValueError("Missing required Reddit API credentials in environment variables")
            
        self.reddit = self._authenticate()
    
    def _authenticate(self) -> praw.Reddit:
        """Authenticate with the Reddit API."""
        try:
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
                username=self.username,
                password=self.password
            )
            
            # Test the connection
            if not reddit.user.me():
                raise ValueError("Failed to authenticate with Reddit API")
                
            logger.info(f"Successfully authenticated as u/{reddit.user.me()}")
            return reddit
            
        except Exception as e:
            logger.error(f"Reddit authentication failed: {e}")
            raise
    
    def search_posts(self, query: str, subreddits: List[str] = None, 
                    limit: int = 10, sort: str = 'relevance', 
                    time_filter: str = 'all') -> List[RedditPost]:
        """Search for posts across Reddit or specific subreddits.
        
        Args:
            query: Search query string
            subreddits: List of subreddits to search in (None for all of Reddit)
            limit: Maximum number of posts to return (max 1000)
            sort: How to sort results ('relevance', 'hot', 'top', 'new', 'comments')
            time_filter: Time period to search ('all', 'day', 'hour', 'month', 'week', 'year')
            
        Returns:
            List of RedditPost objects
        """
        try:
            query = self._build_query(query, subreddits)
            results = []
            
            # Search using PRAW
            submissions = self.reddit.subreddit('all').search(
                query=query,
                limit=min(100, limit),  # PRAW's default limit is 100
                sort=sort,
                time_filter=time_filter
            )
            
            for submission in submissions:
                try:
                    post = RedditPost(
                        id=submission.id,
                        title=submission.title,
                        selftext=submission.selftext,
                        score=submission.score,
                        subreddit=submission.subreddit.display_name.lower(),
                        url=submission.url,
                        permalink=f"https://www.reddit.com{submission.permalink}",
                        created_utc=submission.created_utc,
                        num_comments=submission.num_comments,
                        author=str(submission.author) if submission.author else '[deleted]',
                        is_self=submission.is_self
                    )
                    results.append(post)
                    
                    if len(results) >= limit:
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing submission {submission.id}: {e}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"Error in search_posts: {e}")
            return []
    
    def get_subreddit_posts(self, subreddit: str, limit: int = 10, 
                          sort: str = 'hot', time_filter: str = 'day') -> List[RedditPost]:
        """Get posts from a specific subreddit.
        
        Args:
            subreddit: Name of the subreddit (without r/)
            limit: Maximum number of posts to return (max 1000)
            sort: How to sort posts ('hot', 'new', 'top', 'rising')
            time_filter: Time period for top posts ('hour', 'day', 'week', 'month', 'year', 'all')
            
        Returns:
            List of RedditPost objects
        """
        try:
            subreddit = self.reddit.subreddit(subreddit)
            results = []
            
            # Get submissions based on sort type
            if sort == 'hot':
                submissions = subreddit.hot(limit=limit)
            elif sort == 'new':
                submissions = subreddit.new(limit=limit)
            elif sort == 'top':
                submissions = subreddit.top(time_filter=time_filter, limit=limit)
            elif sort == 'rising':
                submissions = subreddit.rising(limit=limit)
            else:
                submissions = subreddit.hot(limit=limit)
            
            for submission in submissions:
                try:
                    post = RedditPost(
                        id=submission.id,
                        title=submission.title,
                        selftext=submission.selftext,
                        score=submission.score,
                        subreddit=subreddit.display_name.lower(),
                        url=submission.url,
                        permalink=f"https://www.reddit.com{submission.permalink}",
                        created_utc=submission.created_utc,
                        num_comments=submission.num_comments,
                        author=str(submission.author) if submission.author else '[deleted]',
                        is_self=submission.is_self
                    )
                    results.append(post)
                    
                    if len(results) >= limit:
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing submission {submission.id}: {e}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"Error in get_subreddit_posts: {e}")
            return []
    
    def _build_query(self, query: str, subreddits: List[str] = None) -> str:
        """Build a search query string for Reddit's search."""
        query = query.strip()
        
        if subreddits and len(subreddits) > 0:
            # Format subreddits as "subreddit:name1+subreddit:name2"
            subreddit_query = " OR ".join(f"subreddit:{sr.lower().replace('r/', '')}" 
                                         for sr in subreddits)
            return f"({query}) AND ({subreddit_query})"
            
        return query

# Example usage
if __name__ == "__main__":
    # Test the client
    client = RedditClient()
    
    # Search for posts
    print("Searching for 'python' in r/learnpython...")
    posts = client.search_posts("python", ["learnpython"], limit=3)
    for i, post in enumerate(posts, 1):
        print(f"{i}. {post.title} (r/{post.subreddit}, {post.score} points)")
    
    # Get hot posts from a subreddit
    print("\nHot posts from r/programming:")
    posts = client.get_subreddit_posts("programming", limit=3, sort="hot")
    for i, post in enumerate(posts, 1):
        print(f"{i}. {post.title} ({post.score} points, {post.num_comments} comments)")
