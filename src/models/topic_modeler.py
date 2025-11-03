from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import pairwise_distances
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
from dataclasses import dataclass
import umap.umap_ as umap
import hdbscan
import logging

logger = logging.getLogger(__name__)

@dataclass
class Topic:
    """Represents a topic with its key terms and example posts."""
    id: int
    label: str
    key_terms: List[str]
    example_posts: List[Dict]
    size: int
    sentiment: float
    
class TopicModeler:
    """Handles topic modeling and document clustering."""
    
    def __init__(self, 
                 min_cluster_size: int = 5,
                 min_samples: int = 2,
                 n_components: int = 5,
                 random_state: int = 42):
        """Initialize the topic modeler.
        
        Args:
            min_cluster_size: Minimum size of clusters
            min_samples: Minimum samples for HDBSCAN
            n_components: Number of components for UMAP
            random_state: Random seed for reproducibility
        """
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.n_components = n_components
        self.random_state = random_state
        
        # Initialize models
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.umap_reducer = umap.UMAP(
            n_components=n_components,
            random_state=random_state
        )
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            gen_min_span_tree=True
        )
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words='english',
            max_features=5000
        )
    
    def extract_topics(self, 
                      texts: List[str], 
                      metadata: List[Dict] = None) -> List[Topic]:
        """Extract topics from a list of texts.
        
        Args:
            texts: List of text documents
            metadata: Optional list of metadata dicts for each text
            
        Returns:
            List of Topic objects
        """
        if not texts:
            return []
            
        if metadata is None:
            metadata = [{}] * len(texts)
            
        # Generate embeddings
        logger.info("Generating document embeddings...")
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
        
        # Reduce dimensionality
        logger.info("Reducing dimensions with UMAP...")
        reduced_embeddings = self.umap_reducer.fit_transform(embeddings)
        
        # Cluster documents
        logger.info("Clustering documents...")
        clusters = self.clusterer.fit_predict(reduced_embeddings)
        
        # Extract topics
        topics = []
        unique_clusters = set(clusters) - {-1}  # Exclude noise
        
        # Get TF-IDF features for each cluster
        tfidf = self.vectorizer.fit_transform(texts)
        feature_names = self.vectorizer.get_feature_names_out()
        
        for cluster_id in unique_clusters:
            # Get documents in this cluster
            mask = clusters == cluster_id
            cluster_texts = [texts[i] for i, m in enumerate(mask) if m]
            cluster_meta = [metadata[i] for i, m in enumerate(mask) if m]
            
            # Skip small clusters
            if len(cluster_texts) < self.min_cluster_size:
                continue
                
            # Get TF-IDF scores for this cluster
            cluster_tfidf = tfidf[mask]
            cluster_tfidf = np.asarray(cluster_tfidf.mean(axis=0)).ravel()
            
            # Get top terms
            top_indices = np.argsort(cluster_tfidf)[::-1][:10]
            top_terms = [feature_names[i] for i in top_indices 
                        if cluster_tfidf[i] > 0]
            
            # Get example posts (highest scoring by TF-IDF)
            doc_scores = np.asarray(cluster_tfidf).sum(axis=1)
            example_indices = np.argsort(doc_scores)[::-1][:3]
            example_posts = [{
                'text': cluster_texts[i],
                **cluster_meta[i],
                'score': float(doc_scores[i])
            } for i in example_indices]
            
            # Create topic
            topic = Topic(
                id=int(cluster_id),
                label=' • '.join(top_terms[:3]),
                key_terms=top_terms,
                example_posts=example_posts,
                size=int(mask.sum()),
                sentiment=0.0  # Will be updated later
            )
            topics.append(topic)
        
        return topics
    
    def find_similar_documents(self, 
                             query: str, 
                             documents: List[str],
                             k: int = 5) -> List[Tuple[int, float]]:
        """Find documents similar to the query.
        
        Args:
            query: Search query
            documents: List of documents to search in
            k: Number of results to return
            
        Returns:
            List of (index, score) tuples
        """
        if not documents:
            return []
            
        # Get query embedding
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Get document embeddings
        doc_embeddings = self.embedding_model.encode(documents)
        
        # Calculate similarities
        similarities = 1 - pairwise_distances(
            [query_embedding], 
            doc_embeddings, 
            metric='cosine'
        )[0]
        
        # Get top k results
        top_indices = np.argsort(similarities)[::-1][:k]
        return [(i, float(similarities[i])) for i in top_indices]
    
    def get_document_clusters(self, 
                            texts: List[str],
                            n_clusters: int = 5) -> Tuple[np.ndarray, List[str]]:
        """Cluster documents and return cluster labels and top terms.
        
        Args:
            texts: List of text documents
            n_clusters: Number of clusters
            
        Returns:
            Tuple of (cluster_labels, cluster_terms)
        """
        if not texts:
            return np.array([]), []
            
        # Get document embeddings
        embeddings = self.embedding_model.encode(texts)
        
        # Reduce dimensions
        reduced_embeddings = self.umap_reducer.fit_transform(embeddings)
        
        # Cluster
        kmeans = KMeans(n_clusters=min(n_clusters, len(texts)), 
                       random_state=self.random_state)
        cluster_labels = kmeans.fit_predict(reduced_embeddings)
        
        # Get top terms per cluster
        tfidf = self.vectorizer.fit_transform(texts)
        feature_names = self.vectorizer.get_feature_names_out()
        
        cluster_terms = []
        for i in range(n_clusters):
            cluster_tfidf = tfidf[cluster_labels == i]
            if cluster_tfidf.shape[0] == 0:
                cluster_terms.append("")
                continue
                
            cluster_tfidf = np.asarray(cluster_tfidf.mean(axis=0)).ravel()
            top_indices = np.argsort(cluster_tfidf)[::-1][:5]
            terms = [feature_names[i] for i in top_indices 
                    if cluster_tfidf[i] > 0]
            cluster_terms.append(" • ".join(terms[:3]))
        
        return cluster_labels, cluster_terms
