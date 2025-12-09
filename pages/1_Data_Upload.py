import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
from pathlib import Path
import io
import tempfile
import chardet
from typing import Optional, Dict, Any, List, Union
import base64

# Import core modules
from core.auth import require_auth, get_current_user, require_role
from core.database import save_dataset, get_user_datasets, get_public_datasets, get_db_connection
from core.config import ensure_app_dirs, UPLOAD_DIR, PROCESSED_DIR
from core.reddit_utils import get_reddit_topic_data

# Import Gemini API for data analysis
import google.generativeai as genai

# Set page config
st.set_page_config(
    page_title="Data Sources | Big Data Analytics Platform",
    page_icon="📊",
    layout="wide"
)

# Initialize Gemini API
gemini_model = None
try:
    # Configure with the API key
    genai.configure(api_key="AIzaSyD43a-TYmk9tycX5LbHM74rgMZZlU5NyXM")
    
    # List available models and select the most appropriate one
    available_models = [m for m in genai.list_models() 
                       if 'generateContent' in m.supported_generation_methods]
    
    # Prefer newer models, fall back to others if needed
    model_preference_order = [
        'gemini-1.5-pro-latest',
        'gemini-1.5-flash-latest',
        'gemini-1.0-pro-latest',
        'gemini-pro',
        'models/text-bison-001'  # Fallback model
    ]
    
    selected_model = next((m for m in model_preference_order 
                         if m in [model.name.split('/')[-1] for model in available_models]), None)
    
    if selected_model:
        gemini_model = genai.GenerativeModel(selected_model)
        st.session_state.gemini_model_name = selected_model
    else:
        st.warning("No suitable Gemini model found. Some AI features will be disabled.")
        
except Exception as e:
    st.warning(f"AI features are currently unavailable. Error: {str(e)}")
    if 'gemini_model' in locals():
        gemini_model = None

# Ensure required directories exist
ensure_app_dirs()

# Require authentication
require_auth()
user = get_current_user()

# Page title and description
st.title("📊 Data Sources")
st.markdown("""
    Upload and manage your datasets in various formats (CSV, Excel, JSON, etc.).
    The platform will automatically process and clean your data for analysis.
""")

# Initialize session state for datasets
if 'datasets' not in st.session_state:
    st.session_state.datasets = []

# Initialize session state for active dataset
if 'active_dataset' not in st.session_state:
    st.session_state.active_dataset = None

# Initialize session state for data cleaning steps
if 'cleaning_steps' not in st.session_state:
    st.session_state.cleaning_steps = []

def detect_encoding(file_path):
    """Detect the encoding of a file."""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(10000))
    return result['encoding']

def load_dataframe(file, file_type):
    """Load data from different file types into a pandas DataFrame."""
    try:
        # Create a temporary file to save the uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp_file:
            tmp_file.write(file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Detect file type and load accordingly
        if file_type in ['csv', 'txt']:
            # Detect encoding for CSV and text files
            encoding = detect_encoding(tmp_file_path)
            df = pd.read_csv(tmp_file_path, encoding=encoding, low_memory=False)
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(tmp_file_path, engine='openpyxl')
        elif file_type == 'json':
            df = pd.read_json(tmp_file_path)
        else:
            st.error(f"Unsupported file type: {file_type}")
            return None
        
        # Clean up temporary file
        os.unlink(tmp_file_path)
        return df
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        return None

def clean_data(df):
    """Clean the dataset with various data cleaning techniques."""
    cleaning_steps = []
    original_shape = df.shape
    
    # Create a copy to avoid modifying the original
    df_cleaned = df.copy()
    
    # 1. Handle missing values
    missing_before = df_cleaned.isnull().sum().sum()
    
    # For numeric columns, fill with mean or median
    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if df_cleaned[col].isnull().sum() > 0:
            # Use median for skewed data, mean for normal distribution
            if abs(df_cleaned[col].skew()) > 1:  # If highly skewed
                df_cleaned[col].fillna(df_cleaned[col].median(), inplace=True)
                method = 'median'
            else:
                df_cleaned[col].fillna(df_cleaned[col].mean(), inplace=True)
                method = 'mean'
            
            cleaned_count = df_cleaned[col].isnull().sum()
            cleaning_steps.append({
                'step': 'Missing Values',
                'details': f'Filled {cleaned_count} missing values in {col} with {method}',
                'impact': f'Improved data completeness for {col}'
            })
    
    # For categorical columns, fill with mode or 'Unknown'
    categorical_cols = df_cleaned.select_dtypes(include=['object', 'category']).columns
    for col in categorical_cols:
        if df_cleaned[col].isnull().sum() > 0:
            mode_val = df_cleaned[col].mode()[0] if not df_cleaned[col].mode().empty else 'Unknown'
            df_cleaned[col].fillna(mode_val, inplace=True)
            
            cleaned_count = df_cleaned[col].isnull().sum()
            cleaning_steps.append({
                'step': 'Missing Values',
                'details': f'Filled {cleaned_count} missing values in {col} with mode: {mode_val}',
                'impact': f'Improved data completeness for {col}'
            })
    
    missing_after = df_cleaned.isnull().sum().sum()
    
    if missing_before > 0:
        cleaning_steps.append({
            'step': 'Missing Values Summary',
            'details': f'Total missing values handled: {missing_before - missing_after}',
            'impact': 'Improved overall data quality by handling missing values'
        })
    
    # 2. Remove duplicate rows
    duplicates = df_cleaned.duplicated().sum()
    if duplicates > 0:
        df_cleaned = df_cleaned.drop_duplicates()
        cleaning_steps.append({
            'step': 'Duplicate Rows',
            'details': f'Removed {duplicates} duplicate rows',
            'impact': 'Improved data quality by removing duplicates'
        })
    
    # 3. Convert data types
    for col in df_cleaned.columns:
        # Check if column contains date-like strings
        if df_cleaned[col].dtype == 'object':
            try:
                # Try to convert to datetime
                df_cleaned[col] = pd.to_datetime(df_cleaned[col], errors='ignore')
                if pd.api.types.is_datetime64_any_dtype(df_cleaned[col]):
                    cleaning_steps.append({
                        'step': 'Data Type Conversion',
                        'details': f'Converted {col} to datetime',
                        'impact': 'Improved data type consistency for temporal analysis'
                    })
            except:
                pass
    
    # 4. Handle outliers for numeric columns
    for col in numeric_cols:
        # Skip if column has low variance or is binary
        if df_cleaned[col].nunique() <= 2:
            continue
            
        # Calculate IQR
        Q1 = df_cleaned[col].quantile(0.25)
        Q3 = df_cleaned[col].quantile(0.75)
        IQR = Q3 - Q1
        
        # Define bounds
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Count outliers
        outliers = ((df_cleaned[col] < lower_bound) | (df_cleaned[col] > upper_bound)).sum()
        
        if outliers > 0:
            # Cap outliers to the bounds
            df_cleaned[col] = np.where(df_cleaned[col] < lower_bound, lower_bound, df_cleaned[col])
            df_cleaned[col] = np.where(df_cleaned[col] > upper_bound, upper_bound, df_cleaned[col])
            
            cleaning_steps.append({
                'step': 'Outlier Handling',
                'details': f'Capped {outliers} outliers in {col}',
                'impact': 'Reduced impact of extreme values on analysis'
            })
    
    # 5. Standardize text data
    for col in categorical_cols:
        # Convert to string and strip whitespace
        df_cleaned[col] = df_cleaned[col].astype(str).str.strip()
        
        # Standardize case (title case for names, upper for codes, etc.)
        if df_cleaned[col].str.isupper().mean() > 0.7:  # If mostly uppercase
            df_cleaned[col] = df_cleaned[col].str.upper()
        elif df_cleaned[col].str.istitle().mean() > 0.7:  # If mostly title case
            df_cleaned[col] = df_cleaned[col].str.title()
        else:
            df_cleaned[col] = df_cleaned[col].str.capitalize()
    
    # 6. Generate data quality report
    final_shape = df_cleaned.shape
    
    cleaning_steps.append({
        'step': 'Data Cleaning Summary',
        'details': f'Original shape: {original_shape} | Cleaned shape: {final_shape}',
        'impact': f'Data quality improved, {original_shape[0] - final_shape[0]} rows removed'
    })
    
    return df_cleaned, cleaning_steps

def analyze_with_gemini(df, analysis_type="general"):
    """
    Use Gemini API to analyze the dataset with enhanced error handling
    and model-specific optimizations.
    """
    if gemini_model is None:
        return "Gemini API is not available. Please check your API key and internet connection."
    
    try:
        # Convert dataframe to CSV string for analysis
        sample_size = min(100, len(df))  # Use up to 100 rows for analysis
        csv_data = df.head(sample_size).to_csv(index=False)
        
        # Prepare the analysis prompt based on the type
        if analysis_type == "general":
            prompt = {
                "parts": [{"text": f"""
                You are a senior data analyst. Please analyze this dataset and provide insights.
                
                Dataset (first {sample_size} rows):
                {csv_data}
                
                Please provide:
                1. Data structure and summary statistics
                2. Key patterns or trends in the data
                3. Potential data quality issues
                4. Suggestions for further analysis
                5. Recommended visualizations
                
                Format your response in clear markdown with appropriate sections.
                """}]
            }
        elif analysis_type == "cleaning":
            prompt = {
                "parts": [{"text": f"""
                You are a data cleaning expert. Analyze this dataset and suggest cleaning steps.
                
                Dataset (first {sample_size} rows):
                {csv_data}
                
                Please provide specific recommendations for:
                1. Handling missing values (counts and imputation strategies)
                2. Identifying and addressing outliers
                3. Data type conversions needed
                4. Potential data quality issues
                5. Feature engineering opportunities
                
                Format your response in clear markdown with code examples where appropriate.
                """}]
            }
        else:
            prompt = {
                "parts": [{"text": f"""
                {analysis_type}
                
                Dataset (first {sample_size} rows):
                {csv_data}
                """}]
            }
        
        # Generate content with error handling
        response = gemini_model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            },
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
            ]
        )
        
        # Extract and format the response
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'parts') and response.parts:
            return "\n".join(part.text for part in response.parts if hasattr(part, 'text'))
        else:
            return "Received an unexpected response format from the model."
            
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower():
            return "API quota exceeded. Please try again later or check your API key's usage limits."
        elif "unavailable" in error_msg.lower():
            return "The AI service is currently unavailable. Please try again later."
        else:
            return f"Error analyzing data: {error_msg}"

def save_uploaded_file(uploaded_file, filename, user_id, description=None):
    """
    Save the uploaded file and store its metadata in the database.
    Returns (success, message, dataset_id)
    """
    try:
        # Create necessary directories
        user_upload_dir = os.path.join(UPLOAD_DIR, str(user_id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Generate safe filename and path
        timestamp = int(datetime.now().timestamp())
        file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(user_upload_dir, safe_filename)
        
        # Save the file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Read the file to get metadata
        df = pd.read_csv(file_path) if file_ext == 'csv' else None
        if df is None:
            return False, "Unsupported file format. Please upload a CSV file.", None
        
        # Prepare dataset metadata
        dataset_metadata = {
            'original_filename': filename,
            'file_size': os.path.getsize(file_path),
            'num_rows': len(df),
            'num_columns': len(df.columns),
            'column_names': df.columns.tolist(),
            'sample_data': df.head(5).to_dict(orient='records') if len(df) > 0 else []
        }
        
        # Save to database using save_dataset function
        dataset_name = os.path.splitext(filename)[0]  # Use filename without extension as name
        dataset_id = save_dataset(
            user_id=user_id,
            name=dataset_name,
            file_path=file_path,
            file_type=file_ext,
            file_name=filename,
            description=description,
            metadata={
                'original_filename': filename,
                'file_size': os.path.getsize(file_path),
                'num_rows': len(df),
                'num_columns': len(df.columns),
                'column_names': df.columns.tolist(),
                'sample_data': df.head(5).to_dict(orient='records') if len(df) > 0 else []
            }
        )
        
        return True, "File uploaded successfully!", dataset_id
        
    except Exception as e:
        # Clean up the file if there was an error
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        return False, f"Error uploading file: {str(e)}", None

# Main layout
col1, col2 = st.columns([2, 1])

with col1:
    # Add tabs for different data source types
    source_type = st.radio(
        "Select Data Source",
        ["File Upload", "Reddit Post"],
        horizontal=True,
        key="data_source_type"
    )
    
    if source_type == "File Upload":
        # File upload section
        st.subheader("Upload New Dataset")
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['csv', 'xlsx', 'xls', 'json', 'txt'],
            help="Supported formats: CSV, Excel (xlsx, xls), JSON, TXT"
        )
        
        if uploaded_file is not None:
            # Process the uploaded file
            file_ext = uploaded_file.name.split('.')[-1].lower()
            df = load_dataframe(uploaded_file, file_ext)
            
            if df is not None:
                st.session_state.active_dataset = {
                    'name': uploaded_file.name,
                    'data': df,
                    'original_data': df.copy(),
                    'file_type': file_ext,
                    'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    
    elif source_type == "Reddit Topic":
        st.subheader("Fetch Reddit Data by Topic")
        
        # Topic input
        topic = st.text_input(
            "Enter a topic to search on Reddit",
            placeholder="e.g., artificial intelligence, climate change, etc.",
            key="reddit_topic"
        )
        
        # Time filter
        time_filter = st.selectbox(
            "Time period",
            ["day", "week", "month", "year", "all"],
            index=2,  # Default to "month"
            help="Time period to search within"
        )
        
        # Advanced options
        with st.expander("Advanced Options"):
            max_posts = st.slider(
                "Maximum number of posts to fetch",
                min_value=1,
                max_value=20,
                value=5,
                step=1
            )
            
            max_comments = st.slider(
                "Maximum comments per post",
                min_value=10,
                max_value=100,
                value=20,
                step=5,
                help="Number of top comments to fetch per post"
            )
        
        if st.button("Fetch Reddit Data", key="fetch_reddit_data"):
            if not topic.strip():
                st.warning("Please enter a topic to search for")
            else:
                with st.spinner(f"Searching Reddit for '{topic}'..."):
                    try:
                        # Get Reddit data for the topic
                        df_reddit, metadata = get_reddit_topic_data(
                            topic=topic,
                            time_filter=time_filter,
                            max_posts=max_posts,
                            max_comments_per_post=max_comments
                        )
                        
                        if df_reddit.empty:
                            st.error("No data found for this topic. Try a different search term or time period.")
                        else:
                            # Create a filename based on the topic
                            safe_topic = "".join(c if c.isalnum() else "_" for c in topic)
                            filename = f"reddit_{safe_topic[:30]}_{int(datetime.now().timestamp())}.csv"
                            
                            # Save to uploaded files directory
                            file_path = UPLOAD_DIR / filename
                            df_reddit.to_csv(file_path, index=False)
                            
                            # Extract subreddits for the description
                            subreddits = ", ".join(f"r/{s}" for s in metadata.get('subreddits', []))
                            
                            # Save to database
                            dataset_id = save_dataset(
                                user_id=user['user_id'],
                                name=f"Reddit: {topic[:50]}",
                                file_path=str(file_path),
                                file_type='csv',
                                file_name=filename,
                                description=f"Reddit data for topic: {topic}. Posts from {subreddits}.",
                                metadata={
                                    'source': 'reddit',
                                    'topic': topic,
                                    'time_filter': time_filter,
                                    'num_posts': metadata.get('num_posts', 0),
                                    'num_comments': metadata.get('num_comments', 0),
                                    'subreddits': metadata.get('subreddits', []),
                                    'posts': metadata.get('posts', [])
                                }
                            )
                            
                            # Store in session state
                            st.session_state.active_dataset = {
                                'id': dataset_id,
                                'name': f"Reddit: {topic[:50]}",
                                'data': df_reddit,
                                'original_data': df_reddit.copy(),
                                'file_type': 'csv',
                                'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'cleaning_steps': [{
                                    'step': 'Data Collection',
                                    'details': f"Collected {metadata.get('num_posts', 0)} posts and {metadata.get('num_comments', 0)} comments from Reddit about '{topic}'",
                                    'impact': 'Initial data collection from Reddit',
                                    'subreddits': metadata.get('subreddits', [])
                                }]
                            }
                            
                            st.success(
                                f"Successfully fetched {metadata.get('num_posts', 0)} posts and "
                                f"{metadata.get('num_comments', 0)} comments from Reddit about '{topic}'"
                            )
                            
                            # Show a preview of the data
                            st.subheader("Data Preview")
                            st.dataframe(df_reddit.head())
                            
                            # Show some statistics
                            st.subheader("Dataset Statistics")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Posts", metadata.get('num_posts', 0))
                            with col2:
                                st.metric("Total Comments", metadata.get('num_comments', 0))
                            with col3:
                                st.metric("Subreddits", len(metadata.get('subreddits', [])))
                            
                            # Show a sample of subreddits
                            if metadata.get('subreddits'):
                                st.write("**Subreddits:**", ", ".join(f"r/{s}" for s in metadata['subreddits']))
                    
                    except Exception as e:
                        st.error(f"An error occurred while fetching Reddit data: {str(e)}")
                        st.exception(e)  # Show full error for debugging
                
                # Save the cleaned dataset
                cleaned_filename = f"cleaned_{int(datetime.now().timestamp())}.csv"
                cleaned_filepath = os.path.join(PROCESSED_DIR, cleaned_filename)
                df_cleaned.to_csv(cleaned_filepath, index=False)
                
                # Save dataset info to database
                dataset_id = save_dataset(
                    user_id=user['user_id'],
                    name=uploaded_file.name,
                    file_path=file_path,
                    file_type=file_ext,
                    description=f"Uploaded by {user['username']} on {datetime.now().strftime('%Y-%m-%d')}",
                    metadata={
                        'original_columns': list(df.columns),
                        'cleaned_columns': list(df_cleaned.columns),
                        'original_shape': df.shape,
                        'cleaned_shape': df_cleaned.shape,
                        'cleaning_steps': cleaning_steps
                    }
                )
                
                st.session_state.active_dataset['id'] = dataset_id
                st.session_state.active_dataset['cleaned_filepath'] = cleaned_filepath
                
                st.success("Dataset uploaded and cleaned successfully!")

with col2:
    # Display dataset info if available
    if st.session_state.active_dataset is not None:
        dataset = st.session_state.active_dataset
        st.subheader("Dataset Info")
        st.write(f"**Name:** {dataset['name']}")
        st.write(f"**Type:** {dataset.get('file_type', 'N/A').upper()}")
        st.write(f"**Uploaded:** {dataset.get('uploaded_at', 'N/A')}")
        
        # Handle shape display for both original and cleaned data
        if 'original_data' in dataset and hasattr(dataset['original_data'], 'shape'):
            st.write(f"**Original Shape:** {dataset['original_data'].shape}")
        
        if 'data' in dataset and hasattr(dataset['data'], 'shape'):
            st.write(f"**Shape:** {dataset['data'].shape}")
        else:
            st.warning("No data available to display")
        
        # Show data preview if data is available
        if 'data' in dataset and dataset['data'] is not None and not dataset['data'].empty:
            with st.expander("Preview Data"):
                st.dataframe(dataset['data'].head())
            
            # Show data types
            with st.expander("Data Types"):
                try:
                    st.json(dict(zip(dataset['data'].dtypes.index.tolist(), 
                                   dataset['data'].dtypes.astype(str).tolist())))
                except Exception as e:
                    st.warning(f"Could not display data types: {str(e)}")
        else:
            st.warning("No data available to display")
        
        # Show missing values if data is available
        if 'data' in dataset and dataset['data'] is not None and not dataset['data'].empty:
            with st.expander("Missing Values"):
                try:
                    missing = dataset['data'].isnull().sum()
                    missing = missing[missing > 0]
                    if len(missing) > 0:
                        st.write("Columns with missing values:")
                        st.bar_chart(missing)
                    else:
                        st.success("No missing values found!")
                except Exception as e:
                    st.warning(f"Could not analyze missing values: {str(e)}")
        else:
            with st.expander("Missing Values"):
                st.warning("No data available to analyze")
        
        # Show statistics if data is available
        if 'data' in dataset and dataset['data'] is not None and not dataset['data'].empty:
            with st.expander("Statistics"):
                try:
                    st.write(dataset['data'].describe())
                except Exception as e:
                    st.warning(f"Could not display statistics: {str(e)}")
        else:
            with st.expander("Statistics"):
                st.warning("No data available to display statistics")

# Show cleaning steps if available
if st.session_state.cleaning_steps:
    st.subheader("Data Cleaning Steps")
    for step in st.session_state.cleaning_steps:
        with st.expander(f"{step['step']}"):
            st.write(step['details'])
            st.caption(f"Impact: {step['impact']}")

# Gemini Analysis Section
if st.session_state.active_dataset is not None and gemini_model is not None:
    st.subheader("AI-Powered Analysis")
    
    analysis_type = st.selectbox(
        "Select analysis type",
        ["general", "cleaning", "trends", "anomalies", "predictive"]
    )
    
    if st.button("Analyze with Gemini"):
        with st.spinner("Analyzing data with Gemini..."):
            analysis_result = analyze_with_gemini(
                st.session_state.active_dataset['data'], 
                analysis_type
            )
            st.markdown("### Analysis Results")
            st.markdown(analysis_result)

# Display datasets with toggle between user's and public datasets
st.subheader("Datasets")

# Toggle between user's datasets and public datasets
view_mode = st.radio(
    "View:",
    ["My Datasets", "Public Datasets"],
    horizontal=True,
    label_visibility="collapsed"
)

if view_mode == "My Datasets":
    datasets = get_user_datasets(user['user_id'])
    if not datasets:
        st.info("You haven't uploaded any datasets yet.")
else:
    # Get public datasets, excluding the current user's datasets
    datasets = get_public_datasets(exclude_user_id=user['user_id'])
    if not datasets:
        st.info("No public datasets available from other users.")

if datasets:
    for dataset in datasets:
        # Different expander title based on whether it's the user's dataset or public
        if view_mode == "My Datasets" or dataset['user_id'] == user['user_id']:
            title = f"{dataset['name']} - {dataset['created_at'].split(' ')[0]}"
        else:
            title = f"{dataset['owner_username']}'s {dataset['name']} - {dataset['created_at'].split(' ')[0]}"
        
        with st.expander(title):
            col1, col2 = st.columns([3, 1])
            with col1:
                # Show owner info for public datasets
                if view_mode == "Public Datasets" or dataset.get('owner_username'):
                    st.write(f"**Owner:** {dataset.get('owner_username', 'You')}")
                
                st.write(f"**Type:** {dataset['file_type'].upper()}")
                st.write(f"**Rows:** {dataset.get('num_rows', 'N/A')}")
                st.write(f"**Columns:** {dataset.get('num_columns', 'N/A')}")
                st.write(f"**Uploaded:** {dataset['created_at']}")
                
                # Show public/private status and toggle for user's own datasets
                if view_mode == "My Datasets" or dataset.get('user_id') == user['user_id']:
                    with st.form(key=f"visibility_{dataset['id']}"):
                        is_public = st.toggle(
                            "Make Public",
                            value=dataset.get('is_public', False),
                            key=f"public_toggle_{dataset['id']}",
                            help="Make this dataset visible to other users"
                        )
                        if st.form_submit_button("Update Visibility"):
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE datasets SET is_public = ? WHERE id = ? AND user_id = ?",
                                    (1 if is_public else 0, dataset['id'], user['user_id'])
                                )
                                conn.commit()
                            st.rerun()
                
                # Load and display dataset info
                load_col, _ = st.columns([1, 3])
                with load_col:
                    if st.button(f"📊 Load {dataset['name']}", key=f"load_{dataset['id']}", 
                               help="Load this dataset for analysis"):
                        try:
                            file_path = dataset['file_path']
                            if not os.path.exists(file_path):
                                st.error("❌ Error: Dataset file not found. It may have been moved or deleted.")
                            else:
                                with st.spinner("Loading dataset..."):
                                    df = pd.read_csv(file_path)
                                    st.session_state.active_dataset = {
                                        'id': dataset['id'],
                                        'name': dataset['name'],
                                        'data': df,
                                        'file_type': dataset['file_type'],
                                        'uploaded_at': dataset['created_at']
                                    }
                                st.success(f"✅ Successfully loaded '{dataset['name']}'")
                                st.rerun()
                        except pd.errors.EmptyDataError:
                            st.error("❌ Error: The dataset file is empty.")
                        except pd.errors.ParserError:
                            st.error("❌ Error: Could not parse the dataset file. It may be corrupted or in an unsupported format.")
                        except Exception as e:
                            st.error(f"❌ Error loading dataset: {str(e)}")
            
            with col2:
                # Add download button
                with open(dataset['file_path'], 'rb') as f:
                    st.download_button(
                        label="Download",
                        data=f,
                        file_name=dataset['name'],
                        mime="application/octet-stream",
                        key=f"dl_{dataset['id']}"
                    )
                
                # Delete button (with confirmation)
                if st.button("Delete", key=f"del_{dataset['id']}"):
                    try:
                        if os.path.exists(dataset['file_path']):
                            os.remove(dataset['file_path'])
                        # Here you would also delete the database record
                        st.success(f"Dataset '{dataset['name']}' deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting dataset: {str(e)}")
else:
    st.info("You haven't uploaded any datasets yet. Use the uploader above to get started.")

# Add custom CSS for better styling
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
    }
    .stDownloadButton>button {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)
