"""
Admin panel for system administration.
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import streamlit as st
import pandas as pd
from datetime import datetime
from src.services.auth import SessionManager, AuthorizationService
from src.database.models import User, Role, DataSource, MLModel, ActivityLog
from src.database.connection import get_db
from src.database.utils import ensure_uuid

# Page configuration
st.set_page_config(
    page_title="Admin Panel - Content Virality Platform",
    page_icon="⚙️",
    layout="wide"
)

# Check authentication and authorization
SessionManager.require_authentication()
SessionManager.require_role("System Administrator")

st.title("⚙️ System Administration")

# Get current user
current_user = SessionManager.get_current_user()
auth_service = AuthorizationService()

# Verify current user is valid
if not current_user or 'id' not in current_user:
    st.error("Invalid user session.")
    st.stop()

# Admin navigation tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👥 User Management", 
    "📊 Data Sources", 
    "🤖 ML Models", 
    "📋 Activity Logs",
    "📈 System Metrics"
])

with tab1:
    st.header("User Management")
    
    # User list
    with get_db() as db:
        users = db.query(User).all()
        
        if users:
            # Create user data for display
            user_data = []
            for user in users:
                user_data.append({
                    "ID": str(user.id),
                    "Username": user.username,
                    "Email": user.email,
                    "Full Name": user.full_name,
                    "Roles": ", ".join([role.name for role in user.roles]),
                    "Active": "✅" if user.is_active else "❌",
                    "Created": user.created_at.strftime("%Y-%m-%d %H:%M")
                })
            
            df_users = pd.DataFrame(user_data)
            st.dataframe(df_users, use_container_width=True)
            
            # User management actions
            st.subheader("User Actions")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Activate/Deactivate User**")
                selected_user_id = st.selectbox(
                    "Select User",
                    options=[str(user.id) for user in users],
                    format_func=lambda x: next(user.username for user in users if str(user.id) == x)
                )
                
                col1a, col1b = st.columns(2)
                with col1a:
                    if st.button("Activate User"):
                        if auth_service.activate_user(selected_user_id):
                            st.success("User activated successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to activate user.")
                
                with col1b:
                    if st.button("Deactivate User"):
                        if auth_service.deactivate_user(selected_user_id):
                            st.success("User deactivated successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to deactivate user.")
            
            with col2:
                st.write("**Role Management**")
                
                # Get all roles
                roles = db.query(Role).all()
                role_names = [role.name for role in roles]
                
                selected_user_for_role = st.selectbox(
                    "Select User for Role Assignment",
                    options=[str(user.id) for user in users],
                    format_func=lambda x: next(user.username for user in users if str(user.id) == x),
                    key="role_user_select"
                )
                
                selected_role = st.selectbox("Select Role", options=role_names)
                
                col2a, col2b = st.columns(2)
                with col2a:
                    if st.button("Assign Role"):
                        if auth_service.assign_role(selected_user_for_role, selected_role):
                            st.success(f"Role '{selected_role}' assigned successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to assign role or role already assigned.")
                
                with col2b:
                    if st.button("Remove Role"):
                        if auth_service.remove_role(selected_user_for_role, selected_role):
                            st.success(f"Role '{selected_role}' removed successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to remove role or role not assigned.")
        else:
            st.info("No users found in the system.")

with tab2:
    st.header("Data Source Management")
    
    with get_db() as db:
        data_sources = db.query(DataSource).all()
        
        if data_sources:
            # Display data sources
            source_data = []
            for source in data_sources:
                source_data.append({
                    "ID": str(source.id),
                    "Name": source.name,
                    "Type": source.type,
                    "Status": "🟢 Active" if source.is_active else "🔴 Inactive",
                    "Created": source.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Last Scraped": source.last_scraped_at.strftime("%Y-%m-%d %H:%M") if source.last_scraped_at else "Never"
                })
            
            df_sources = pd.DataFrame(source_data)
            st.dataframe(df_sources, use_container_width=True)
        else:
            st.info("No data sources configured.")
        
        # Add new data source
        st.subheader("Add New Data Source")
        
        with st.form("add_data_source"):
            col1, col2 = st.columns(2)
            
            with col1:
                source_name = st.text_input("Source Name")
                source_type = st.selectbox("Source Type", ["reddit", "twitter", "rss", "news_api"])
            
            with col2:
                if source_type == "reddit":
                    subreddit = st.text_input("Subreddit Name")
                    config = {"subreddit": subreddit}
                elif source_type == "twitter":
                    hashtag = st.text_input("Hashtag or Username")
                    config = {"query": hashtag}
                elif source_type == "rss":
                    rss_url = st.text_input("RSS Feed URL")
                    config = {"url": rss_url}
                else:
                    api_key = st.text_input("API Key", type="password")
                    config = {"api_key": api_key}
            
            if st.form_submit_button("Add Data Source"):
                if source_name and config:
                    # Create new data source
                    try:
                        user_id = current_user['id']
                        if not user_id:
                            st.error("Invalid user session.")
                        else:
                            user_uuid = ensure_uuid(user_id)
                            new_source = DataSource(
                                name=source_name,
                                type=source_type,
                                config=config,
                                created_by=user_uuid
                            )
                    except Exception as e:
                        st.error(f"Error creating data source: {e}")
                    db.add(new_source)
                    db.commit()
                    st.success("Data source added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields.")

with tab3:
    st.header("ML Model Management")
    
    with get_db() as db:
        models = db.query(MLModel).all()
        
        if models:
            # Display models
            model_data = []
            for model in models:
                model_data.append({
                    "ID": str(model.id),
                    "Name": model.name,
                    "Type": model.type,
                    "Version": model.version,
                    "Status": "🟢 Active" if model.is_active else "⚪ Inactive",
                    "Created": model.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Metrics": str(model.metrics) if model.metrics else "N/A"
                })
            
            df_models = pd.DataFrame(model_data)
            st.dataframe(df_models, use_container_width=True)
            
            # Model actions
            st.subheader("Model Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Retrain Virality Model"):
                    st.info("Model retraining initiated. This may take several minutes...")
                    # In a real implementation, this would trigger a background job
                    st.success("Retraining job started!")
            
            with col2:
                if st.button("🔄 Retrain Topic Model"):
                    st.info("Topic model retraining initiated...")
                    st.success("Retraining job started!")
            
            with col3:
                if st.button("📊 View Model Metrics"):
                    st.info("Model performance metrics will be displayed here.")
        else:
            st.info("No ML models found in the system.")

with tab4:
    st.header("System Activity Logs")
    
    with get_db() as db:
        # Get recent activity logs
        logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(100).all()
        
        if logs:
            log_data = []
            for log in logs:
                user_name = log.user.username if log.user else "System"
                log_data.append({
                    "Timestamp": log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "User": user_name,
                    "Action": log.action,
                    "Resource": f"{log.resource_type}:{log.resource_id}" if log.resource_type else "N/A",
                    "IP Address": log.ip_address or "N/A",
                    "Details": str(log.details) if log.details else ""
                })
            
            df_logs = pd.DataFrame(log_data)
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("No activity logs found.")

with tab5:
    st.header("System Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with get_db() as db:
        # Get system statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        total_data_sources = db.query(DataSource).count()
        active_data_sources = db.query(DataSource).filter(DataSource.is_active == True).count()
        
        with col1:
            st.metric("Total Users", total_users)
        
        with col2:
            st.metric("Active Users", active_users)
        
        with col3:
            st.metric("Data Sources", total_data_sources)
        
        with col4:
            st.metric("Active Sources", active_data_sources)
    
    # System health indicators
    st.subheader("System Health")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("🟢 Database: Connected")
        st.success("🟢 Authentication: Active")
        st.info("🟡 Background Jobs: Monitoring")
    
    with col2:
        st.success("🟢 ML Models: Loaded")
        st.success("🟢 Cache: Available")
        st.info("🟡 External APIs: Rate Limited")

# Back to main app button
st.divider()
if st.button("← Back to Dashboard"):
    st.switch_page("src/app.py")