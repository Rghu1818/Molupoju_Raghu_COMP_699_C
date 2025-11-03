import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any, Optional
from tqdm import tqdm

def analyze_headlines_df(df: pd.DataFrame, subreddits: List[str], time_window: str) -> pd.DataFrame:
    """
    Analyze a DataFrame of headlines and add analysis columns.
    
    Args:
        df: Input DataFrame containing headlines
        subreddits: List of subreddits to analyze trends from
        time_window: Time window for trend analysis ('24h', '7d', '30d')
        
    Returns:
        DataFrame with added analysis columns
    """
    if df.empty:
        return df
    
    # Make a copy to avoid modifying the original
    result_df = df.copy()
    
    # Ensure we have a 'headline' column (case insensitive)
    text_col = next((col for col in df.columns if col.lower() in ['headline', 'title', 'text', 'content']), 
                   df.columns[0] if len(df.columns) > 0 else None)
    
    if text_col is None:
        st.error("No valid text column found in the uploaded file.")
        return df
    
    # Add analysis columns
    tqdm.pandas(desc="Analyzing headlines")
    
    # Import here to avoid circular imports
    from .components import _analyze_headline_virality
    
    # Apply analysis to each row
    analysis_results = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing headlines"):
        headline = row[text_col]
        if pd.isna(headline):
            analysis_results.append({
                'virality_score': 0,
                'sentiment': 0.5,
                'sentiment_label': 'neutral',
                'word_count': 0,
                'has_question': False,
                'has_exclamation': False,
                'has_number': False,
                'trend_matches': []
            })
            continue
            
        analysis = _analyze_headline_virality(str(headline), subreddits, time_window)
        metrics = analysis.get('metrics', {})
        
        # Determine sentiment label
        sentiment_score = metrics.get('sentiment', 0.5)
        if sentiment_score > 0.6:
            sentiment_label = 'positive'
        elif sentiment_score < 0.4:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        analysis_results.append({
            'virality_score': analysis.get('score', 0),
            'sentiment': sentiment_score,
            'sentiment_label': sentiment_label,
            'word_count': metrics.get('word_count', 0),
            'has_question': bool(metrics.get('has_question', 0)),
            'has_exclamation': bool(metrics.get('has_exclamation', 0)),
            'has_number': bool(metrics.get('has_number', 0)),
            'trend_matches': [m[0] for m in metrics.get('trend_matches', [])[:3]]  # Top 3 matches
        })
    
    # Add analysis columns to the result DataFrame
    analysis_df = pd.DataFrame(analysis_results)
    result_df = pd.concat([result_df, analysis_df], axis=1)
    
    return result_df

def render_data_analysis_tab(subreddits: List[str], time_window: str):
    """
    Render the Data Analysis tab with file upload and visualization.
    
    Args:
        subreddits: List of subreddits to analyze trends from
        time_window: Time window for trend analysis ('24h', '7d', '30d')
    """
    st.header("📊 Data Analysis")
    st.write("Upload a CSV file with headlines to analyze their virality, sentiment, and engagement potential.")
    
    # File uploader
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    
    if uploaded_file is not None:
        try:
            # Read the uploaded file
            df = pd.read_csv(uploaded_file)
            
            if df.empty:
                st.warning("The uploaded file is empty.")
                return
                
            st.success(f"Successfully loaded {len(df)} rows from {uploaded_file.name}")
            
            # Show data preview
            with st.expander("View raw data"):
                st.dataframe(df.head())
            
            # Analyze the data
            with st.spinner("Analyzing headlines..."):
                analyzed_df = analyze_headlines_df(df, subreddits, time_window)
            
            # Show analysis results
            st.subheader("Analysis Results")
            
            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average Virality Score", f"{analyzed_df['virality_score'].mean():.1f}")
            with col2:
                st.metric("Positive Sentiment %", 
                         f"{len(analyzed_df[analyzed_df['sentiment_label'] == 'positive']) / len(analyzed_df) * 100:.1f}%")
            with col3:
                st.metric("Avg. Word Count", f"{analyzed_df['word_count'].mean():.1f}")
            
            # Visualizations
            st.subheader("Visualizations")
            
            # Virality distribution
            fig1 = px.histogram(
                analyzed_df, 
                x='virality_score', 
                title='Distribution of Virality Scores',
                labels={'virality_score': 'Virality Score'},
                color_discrete_sequence=['#FF4B4B']
            )
            st.plotly_chart(fig1, use_container_width=True)
            
            # Sentiment distribution
            fig2 = px.pie(
                analyzed_df, 
                names='sentiment_label', 
                title='Sentiment Distribution',
                color='sentiment_label',
                color_discrete_map={
                    'positive': '#2ecc71',
                    'negative': '#e74c3c',
                    'neutral': '#3498db'
                }
            )
            st.plotly_chart(fig2, use_container_width=True)
            
            # Word count vs virality
            if 'word_count' in analyzed_df.columns:
                fig3 = px.scatter(
                    analyzed_df, 
                    x='word_count', 
                    y='virality_score',
                    title='Word Count vs Virality Score',
                    color='sentiment_label',
                    hover_data=[analyzed_df.index],
                    labels={
                        'word_count': 'Word Count',
                        'virality_score': 'Virality Score',
                        'sentiment_label': 'Sentiment'
                    }
                )
                st.plotly_chart(fig3, use_container_width=True)
            
            # Top trend matches
            if 'trend_matches' in analyzed_df.columns:
                st.subheader("Top Trend Matches")
                trend_matches = [item for sublist in analyzed_df['trend_matches'] for item in sublist]
                if trend_matches:
                    trend_counts = pd.Series(trend_matches).value_counts().head(10)
                    if not trend_counts.empty:
                        fig4 = px.bar(
                            trend_counts,
                            title='Most Common Trend Matches',
                            labels={'index': 'Trend Term', 'value': 'Count'},
                            color=trend_counts.values,
                            color_continuous_scale='Viridis'
                        )
                        st.plotly_chart(fig4, use_container_width=True)
                else:
                    st.info("No trend matches found in the analyzed headlines.")
            
            # Download button for analyzed data
            csv = analyzed_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Analyzed Data",
                data=csv,
                file_name='analyzed_headlines.csv',
                mime='text/csv',
            )
            
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
    else:
        st.info("Please upload a CSV file with headlines to analyze.")
