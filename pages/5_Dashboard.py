import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from typing import Optional, Dict, Any

# Core imports
from core.auth import require_auth, get_current_user
from core.storage import Storage
from core.visualization import line_timeseries, heatmap_from_grid
from sqlalchemy import text

# Require authentication
require_auth()
user = get_current_user()

# Initialize storage
if "storage" not in st.session_state:
    st.session_state.storage = Storage()
storage: Storage = st.session_state.storage

# Page title and description
st.title("📊 Data Dashboards")
st.markdown("""
    Create, customize, and explore interactive dashboards with your data.
    Visualize trends, patterns, and insights from Bitcoin prices, IoT sensors, and more.
""")

# Initialize session state for dashboard
if 'selected_table' not in st.session_state:
    st.session_state.selected_table = None
if 'dashboard_visualizations' not in st.session_state:
    st.session_state.dashboard_visualizations = []

# Function to get available tables
def get_available_tables():
    """Get list of tables with data in the database."""
    try:
        with storage.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"))
            tables = [row[0] for row in result.fetchall()]
        return tables
    except Exception as e:
        st.error(f"Error getting tables: {e}")
        return []

# Function to load dataset from table
def load_dataset(table_name: str, limit: int = 1000) -> Optional[pd.DataFrame]:
    """Load data from a database table."""
    try:
        df = storage.read_table(table_name, limit=limit)
        # Convert timestamp columns to datetime
        for col in df.columns:
            if 'ts' in col.lower() or 'time' in col.lower() or 'date' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                except:
                    pass
        return df
    except Exception as e:
        st.error(f"Error loading data from {table_name}: {e}")
        return None

# Function to create visualization
def create_visualization(df: pd.DataFrame, viz_type: str, config: Dict) -> Optional[go.Figure]:
    """Create a visualization based on type and configuration."""
    try:
        if viz_type == 'line':
            fig = px.line(
                df, 
                x=config.get('x_axis'),
                y=config.get('y_axis'),
                title=config.get('title', 'Line Chart'),
                color=config.get('color')
            )
        elif viz_type == 'bar':
            fig = px.bar(
                df,
                x=config.get('x_axis'),
                y=config.get('y_axis'),
                title=config.get('title', 'Bar Chart'),
                color=config.get('color'),
                barmode=config.get('barmode', 'group')
            )
        elif viz_type == 'scatter':
            fig = px.scatter(
                df,
                x=config.get('x_axis'),
                y=config.get('y_axis'),
                title=config.get('title', 'Scatter Plot'),
                color=config.get('color'),
                size=config.get('size')
            )
        elif viz_type == 'histogram':
            fig = px.histogram(
                df,
                x=config.get('x_axis'),
                title=config.get('title', 'Histogram'),
                nbins=config.get('nbins', 30),
                color=config.get('color')
            )
        elif viz_type == 'heatmap':
            # For heatmap, use the visualization module
            if all(col in df.columns for col in ['row', 'col', 'value']):
                fig = heatmap_from_grid(df, row='row', col='col', value='value')
            else:
                st.warning("Heatmap requires 'row', 'col', and 'value' columns")
                return None
        elif viz_type == 'box':
            fig = px.box(
                df,
                x=config.get('x_axis'),
                y=config.get('y_axis'),
                title=config.get('title', 'Box Plot'),
                color=config.get('color')
            )
        else:
            fig = px.line(df, x=df.columns[0], y=df.columns[1] if len(df.columns) > 1 else df.columns[0])
            
        # Update layout
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#2c3e50'),
            margin=dict(l=20, r=20, t=40, b=20),
            height=400
        )
        return fig
    except Exception as e:
        st.error(f"Error creating visualization: {e}")
        return None

# Main dashboard layout
col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("📂 Available Data Sources")
    
    # Get available tables
    tables = get_available_tables()
    
    if not tables:
        st.warning("No data tables found. Please run data ingestion first.")
    else:
        # Filter out system tables
        data_tables = [t for t in tables if t not in ['alert_rules', 'alert_events', 'notification_channels', 'rule_channel_map', 'users']]
        
        if not data_tables:
            st.info("No data tables available yet. Run the Pipelines page to ingest data.")
        else:
            selected_table = st.selectbox(
                "Select a data source", 
                data_tables,
                index=0
            )
            
            if selected_table:
                st.session_state.selected_table = selected_table
                
                # Load data
                limit = st.slider("Rows to load", 100, 5000, 1000, 100)
                df = load_dataset(selected_table, limit)
                
                if df is not None and not df.empty:
                    st.markdown("**Data Preview**")
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    # Show data info
                    st.markdown("**Data Info**")
                    st.json({
                        "Table": selected_table,
                        "Rows": len(df),
                        "Columns": list(df.columns),
                        "Numeric Columns": list(df.select_dtypes(include=['number']).columns),
                        "Date Columns": list(df.select_dtypes(include=['datetime']).columns)
                    })
                    
                    # Add new visualization
                    st.divider()
                    st.markdown("**➕ Create Visualization**")
                    
                    viz_name = st.text_input("Chart Name", f"{selected_table} Chart")
                    viz_type = st.selectbox(
                        "Chart Type",
                        ["line", "bar", "scatter", "histogram", "box", "heatmap"]
                    )
                    
                    # Get numeric and all columns
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    all_cols = df.columns.tolist()
                    
                    # Dynamic form based on chart type
                    if viz_type == 'heatmap':
                        st.info("Heatmap works best with IoT sensor data (row, col, value)")
                    else:
                        x_axis = st.selectbox("X-Axis", all_cols, index=0)
                        
                        if viz_type in ['scatter', 'line', 'bar', 'box']:
                            y_axis = st.selectbox("Y-Axis", numeric_cols if numeric_cols else all_cols, 
                                                index=0 if numeric_cols else 0)
                        else:
                            y_axis = None
                        
                        color_col = st.selectbox("Color By (optional)", [None] + all_cols)
                    
                    if st.button("🎨 Create Chart", use_container_width=True):
                        config = {
                            'x_axis': x_axis if viz_type != 'heatmap' else None,
                            'y_axis': y_axis,
                            'color': color_col,
                            'title': viz_name,
                            'table': selected_table
                        }
                        
                        # Create visualization
                        fig = create_visualization(df, viz_type, config)
                        if fig:
                            # Add to session state
                            st.session_state.dashboard_visualizations.append({
                                'name': viz_name,
                                'type': viz_type,
                                'config': config,
                                'figure': fig,
                                'table': selected_table
                            })
                            st.success(f"✅ {viz_name} created!")
                            st.rerun()
                else:
                    st.warning(f"No data found in {selected_table}")

with col2:
    st.subheader("📈 Your Visualizations")
    
    if st.session_state.dashboard_visualizations:
        # Add clear all button
        col_title, col_clear = st.columns([4, 1])
        with col_clear:
            if st.button("🗑️ Clear All"):
                st.session_state.dashboard_visualizations = []
                st.rerun()
        
        # Display visualizations in a grid
        for idx, viz in enumerate(st.session_state.dashboard_visualizations):
            with st.container():
                col_chart, col_actions = st.columns([5, 1])
                
                with col_chart:
                    st.markdown(f"**{viz['name']}** ({viz['type'].title()} - {viz['table']})")
                    st.plotly_chart(viz['figure'], use_container_width=True)
                
                with col_actions:
                    st.markdown("**Actions**")
                    
                    # Refresh data
                    if st.button("🔄", key=f"refresh_{idx}", help="Refresh data"):
                        df = load_dataset(viz['table'], 1000)
                        if df is not None:
                            new_fig = create_visualization(df, viz['type'], viz['config'])
                            if new_fig:
                                st.session_state.dashboard_visualizations[idx]['figure'] = new_fig
                                st.rerun()
                    
                    # Remove visualization
                    if st.button("❌", key=f"remove_{idx}", help="Remove"):
                        st.session_state.dashboard_visualizations.pop(idx)
                        st.rerun()
                
                st.divider()
    else:
        st.info("📊 No visualizations yet. Select a data source on the left and create your first chart!")
        
        # Show quick start guide
        with st.expander("🚀 Quick Start Guide"):
            st.markdown("""
            ### How to create visualizations:
            
            1. **Select a data source** from the left sidebar
            2. **Choose a chart type** (line, bar, scatter, etc.)
            3. **Configure axes** - select which columns to visualize
            4. **Click "Create Chart"** to add it to your dashboard
            
            ### Available data sources:
            - **btc_prices**: Bitcoin price data over time
            - **iot_sensors**: IoT sensor readings with location data
            - **social_stream**: Social media sentiment data
            
            ### Tips:
            - Use **line charts** for time series data
            - Use **heatmaps** for IoT sensor grid data
            - Use **scatter plots** to find correlations
            - **Refresh** charts to get latest data
            """)

# Add custom CSS
st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 1rem;
    }
    </style>
""", unsafe_allow_html=True)
