from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd
from dataclasses import dataclass
import logging
from pathlib import Path
import json
from datetime import datetime
import hashlib

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class TextFeatures:
    """Container for text features including n-grams, embeddings, and sentiment."""
    text: str
    ngrams: List[str]
    embedding: Optional[np.ndarray] = None
    sentiment: Optional[float] = None
    metadata: Optional[Dict] = None

class TextProcessor:
    """Handles text processing including n-grams, embeddings, and sentiment analysis."""
    
    def __init__(self, ngram_range: Tuple[int, int] = (1, 3)):
        """Initialize the text processor.
        
        Args:
            ngram_range: Range of n-gram sizes to generate (min_n, max_n)
        """
        self.ngram_range = ngram_range
        self.embeddings_model = None
        self.sentiment_model = None
        self._init_models()
    
    def _init_models(self):
        """Lazy load models when needed."""
        try:
            # Using sentence-transformers for embeddings
            from sentence_transformers import SentenceTransformer
            self.embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Using VADER for sentiment analysis (lightweight)
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.sentiment_model = SentimentIntensityAnalyzer()
            
        except ImportError as e:
            logger.warning(f"Could not initialize models: {e}")
    
    def get_ngrams(self, text: str) -> List[str]:
        """Generate n-grams from text."""
        words = text.lower().split()
        ngrams = []
        min_n, max_n = self.ngram_range
        
        for n in range(min_n, max_n + 1):
            ngrams.extend([' '.join(words[i:i+n]) for i in range(len(words)-n+1)])
            
        return ngrams
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Generate text embedding."""
        if not self.embeddings_model:
            self._init_models()
            if not self.embeddings_model:
                raise RuntimeError("Embedding model not available")
                
        return self.embeddings_model.encode([text])[0]
    
    def get_sentiment(self, text: str) -> float:
        """Get sentiment score between -1 (negative) and 1 (positive)."""
        if not self.sentiment_model:
            self._init_models()
            if not self.sentiment_model:
                raise RuntimeError("Sentiment model not available")
                
        return self.sentiment_model.polarity_scores(text)['compound']
    
    def process_text(self, text: str, metadata: Optional[Dict] = None) -> TextFeatures:
        """Process text to extract all features."""
        ngrams = self.get_ngrams(text)
        embedding = self.get_embedding(text)
        sentiment = self.get_sentiment(text)
        
        return TextFeatures(
            text=text,
            ngrams=ngrams,
            embedding=embedding,
            sentiment=sentiment,
            metadata=metadata or {}
        )


class ExperimentTracker:
    """Lightweight experiment tracking with CSV/JSON logging."""
    
    def __init__(self, log_dir: str = "experiments"):
        """Initialize the experiment tracker.
        
        Args:
            log_dir: Directory to store experiment logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_experiment = None
    
    def create_experiment(self, name: str, params: Dict) -> str:
        """Create a new experiment with the given parameters.
        
        Args:
            name: Name of the experiment
            params: Dictionary of parameters
            
        Returns:
            Experiment ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_id = f"{name}_{timestamp}"
        exp_dir = self.log_dir / exp_id
        exp_dir.mkdir(exist_ok=True)
        
        # Save parameters
        with open(exp_dir / "params.json", "w") as f:
            json.dump(params, f, indent=2)
        
        # Initialize metrics file
        metrics_file = exp_dir / "metrics.csv"
        if not metrics_file.exists():
            with open(metrics_file, "w") as f:
                f.write("timestamp,metric,value\n")
        
        self.current_experiment = exp_id
        return exp_id
    
    def log_metrics(self, metrics: Dict[str, float]):
        """Log metrics to the current experiment.
        
        Args:
            metrics: Dictionary of metric names and values
        """
        if not self.current_experiment:
            logger.warning("No active experiment. Call create_experiment first.")
            return
            
        timestamp = datetime.now().isoformat()
        metrics_file = self.log_dir / self.current_experiment / "metrics.csv"
        
        with open(metrics_file, "a") as f:
            for name, value in metrics.items():
                f.write(f"{timestamp},{name},{value}\n")
    
    def log_artifact(self, name: str, data: Dict):
        """Log an artifact (e.g., model weights, predictions).
        
        Args:
            name: Name of the artifact
            data: Data to save (must be JSON-serializable)
        """
        if not self.current_experiment:
            logger.warning("No active experiment. Call create_experiment first.")
            return
            
        artifact_dir = self.log_dir / self.current_experiment / "artifacts"
        artifact_dir.mkdir(exist_ok=True)
        
        # Generate a hash based on the data to avoid duplicates
        data_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        artifact_file = artifact_dir / f"{name}_{data_hash[:8]}.json"
        
        with open(artifact_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_best_experiment(self, metric: str, maximize: bool = True) -> Optional[str]:
        """Get the best experiment ID based on a metric.
        
        Args:
            metric: Name of the metric to optimize
            maximize: Whether to maximize (True) or minimize (False) the metric
            
        Returns:
            ID of the best experiment, or None if no experiments found
        """
        best_exp_id = None
        best_value = -float('inf') if maximize else float('inf')
        
        for exp_dir in self.log_dir.glob("*"):
            metrics_file = exp_dir / "metrics.csv"
            if not metrics_file.exists():
                continue
                
            try:
                df = pd.read_csv(metrics_file)
                metric_df = df[df['metric'] == metric]
                if metric_df.empty:
                    continue
                    
                value = metric_df['value'].iloc[-1]  # Get the last value
                if (maximize and value > best_value) or (not maximize and value < best_value):
                    best_value = value
                    best_exp_id = exp_dir.name
            except Exception as e:
                logger.warning(f"Error processing experiment {exp_dir.name}: {e}")
                continue
                
        return best_exp_id
