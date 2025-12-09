import streamlit as st
from core.auth import require_auth
from core.storage import Storage
from core.ai_assistant import get_assistant, is_gemini_available
import pandas as pd

require_auth()

st.title("🤖 AI Assistant")

if not is_gemini_available():
    st.error("⚠️ Gemini AI is not available. Please check your API key configuration in `core/config.py`.")
    st.info("Set the `GEMINI_API_KEY` variable with a valid Google Gemini API key.")
    st.stop()

st.success("✅ Gemini AI is connected and ready!")

if "storage" not in st.session_state:
    st.session_state.storage = Storage()
storage: Storage = st.session_state.storage

# Initialize chat history
if "ai_chat_history" not in st.session_state:
    st.session_state.ai_chat_history = []

# Tabs for different AI features
tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Chat Assistant",
    "📊 Data Analysis",
    "🔍 Query Helper",
    "📈 Insights Generator"
])

with tab1:
    st.subheader("Chat with AI about your data")
    
    # Display chat history
    for msg in st.session_state.ai_chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your data..."):
        # Add user message
        st.session_state.ai_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    assistant = get_assistant()
                    
                    # Try to get relevant data context
                    context = "Big Data Analytics Platform - User query about data analysis"
                    try:
                        # Get sample data from available tables
                        tables = ["btc_prices", "iot_sensors"]
                        sample_data = {}
                        for table in tables:
                            try:
                                df = storage.read_table(table, limit=10)
                                if not df.empty:
                                    sample_data[table] = df
                            except:
                                pass
                        
                        if sample_data:
                            context += f"\n\nAvailable data tables: {', '.join(sample_data.keys())}"
                    except:
                        pass
                    
                    # Generate response
                    full_prompt = f"{context}\n\nUser question: {prompt}"
                    response = assistant.generate_response(full_prompt)
                    
                    st.write(response)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": error_msg})
    
    if st.button("Clear Chat History"):
        st.session_state.ai_chat_history = []
        st.rerun()

with tab2:
    st.subheader("Analyze Your Data with AI")
    
    table_choice = st.selectbox("Select table to analyze:", ["btc_prices", "iot_sensors"], key="analyze_table")
    limit = st.number_input("Number of rows to analyze:", 10, 1000, 100, key="analyze_limit")
    
    if st.button("Analyze Data", key="analyze_btn"):
        with st.spinner("Loading and analyzing data..."):
            try:
                df = storage.read_table(table_choice, limit=limit)
                
                if df.empty:
                    st.warning("No data available in this table.")
                else:
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    assistant = get_assistant()
                    insights = assistant.generate_data_insights(
                        df,
                        f"{table_choice} data from the Big Data Analytics Platform"
                    )
                    
                    st.markdown("### 🔍 AI Analysis Results")
                    st.write(insights)
                    
                    # Additional statistics
                    with st.expander("📊 Detailed Statistics"):
                        st.write(df.describe())
            except Exception as e:
                st.error(f"Error: {e}")

with tab3:
    st.subheader("Natural Language to SQL")
    st.caption("Describe what you want to query in plain English")
    
    # Get available tables
    try:
        from sqlalchemy import text
        with storage.engine.connect() as conn:
            tables_result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = [row[0] for row in tables_result.fetchall()]
        
        # Get schema
        table_schema = {}
        for table in tables:
            with storage.engine.connect() as conn:
                schema_result = conn.execute(text(f"PRAGMA table_info({table});"))
                columns = [row[1] for row in schema_result.fetchall()]
                table_schema[table] = columns
        
        st.info(f"📊 Available tables: {', '.join(tables)}")
        
        # Show schema
        with st.expander("View Database Schema"):
            for table, cols in table_schema.items():
                st.write(f"**{table}**: {', '.join(cols)}")
        
        nl_query = st.text_area(
            "Describe your query:",
            placeholder="e.g., Show me the top 10 highest Bitcoin prices with their timestamps",
            height=100,
            key="nl_query"
        )
        
        col1, col2 = st.columns([1, 3])
        with col1:
            generate = st.button("🤖 Generate SQL", key="gen_sql_btn")
        with col2:
            auto_execute = st.checkbox("Auto-execute query", value=False)
        
        if generate and nl_query:
            with st.spinner("Generating SQL..."):
                try:
                    assistant = get_assistant()
                    sql = assistant.natural_language_to_sql(nl_query, table_schema)
                    
                    st.code(sql, language="sql")
                    
                    if auto_execute:
                        try:
                            with storage.engine.connect() as conn:
                                result = conn.execute(text(sql))
                                rows = result.fetchall()
                                cols = result.keys()
                            
                            result_df = pd.DataFrame(rows, columns=cols)
                            st.success("✅ Query executed successfully!")
                            st.dataframe(result_df, use_container_width=True)
                        except Exception as e:
                            st.error(f"Query execution error: {e}")
                except Exception as e:
                    st.error(f"Error generating SQL: {e}")
    except Exception as e:
        st.error(f"Error loading database schema: {e}")

with tab4:
    st.subheader("Generate Insights from Any Data")
    st.caption("Upload or select data to get AI-powered insights")
    
    insight_source = st.radio("Data source:", ["Existing Table", "Custom Query"], key="insight_source")
    
    df_to_analyze = None
    
    if insight_source == "Existing Table":
        table = st.selectbox("Select table:", ["btc_prices", "iot_sensors"], key="insight_table")
        rows = st.number_input("Rows to analyze:", 10, 1000, 100, key="insight_rows")
        
        if st.button("Load Data", key="load_insight_data"):
            try:
                df_to_analyze = storage.read_table(table, limit=rows)
                st.session_state.insight_df = df_to_analyze
                st.success(f"Loaded {len(df_to_analyze)} rows")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        custom_sql = st.text_area("Enter SQL query:", height=100, key="custom_insight_sql")
        if st.button("Execute Query", key="exec_insight_query"):
            try:
                from sqlalchemy import text
                with storage.engine.connect() as conn:
                    result = conn.execute(text(custom_sql))
                    rows = result.fetchall()
                    cols = result.keys()
                df_to_analyze = pd.DataFrame(rows, columns=cols)
                st.session_state.insight_df = df_to_analyze
                st.success(f"Query returned {len(df_to_analyze)} rows")
            except Exception as e:
                st.error(f"Error: {e}")
    
    # Show loaded data
    if "insight_df" in st.session_state and st.session_state.insight_df is not None:
        st.dataframe(st.session_state.insight_df.head(10), use_container_width=True)
        
        insight_type = st.multiselect(
            "What insights would you like?",
            ["General Patterns", "Anomalies", "Trends", "Recommendations"],
            default=["General Patterns"]
        )
        
        custom_question = st.text_input(
            "Or ask a specific question about this data:",
            placeholder="e.g., What are the main trends in this data?"
        )
        
        if st.button("🔮 Generate Insights", key="gen_insights_btn"):
            with st.spinner("Analyzing data..."):
                try:
                    assistant = get_assistant()
                    
                    if custom_question:
                        # Answer specific question
                        answer = assistant.chat_about_data(
                            custom_question,
                            st.session_state.insight_df,
                            "User-selected data from analytics platform"
                        )
                        st.markdown("### 💡 Answer")
                        st.write(answer)
                    else:
                        # Generate general insights
                        insights = assistant.generate_data_insights(
                            st.session_state.insight_df,
                            f"Analytics data - Focus on: {', '.join(insight_type)}"
                        )
                        st.markdown("### 💡 Insights")
                        st.write(insights)
                except Exception as e:
                    st.error(f"Error: {e}")

# Footer
st.divider()
st.caption("Powered by Google Gemini AI")
