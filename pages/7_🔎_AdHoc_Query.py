import streamlit as st
import pandas as pd
from sqlalchemy import text
from core.auth import require_auth
from core.storage import Storage
from core.ai_assistant import get_assistant, is_gemini_available

require_auth()

st.title("🔎 Ad-hoc Query")

if "storage" not in st.session_state:
    st.session_state.storage = Storage()
storage: Storage = st.session_state.storage

# Check if AI is available
ai_available = is_gemini_available()

# Add tabs for SQL and Natural Language
tab1, tab2 = st.tabs(["SQL Query", "🤖 Ask in Natural Language"])

with tab1:
    st.caption("Run SQL against the local SQLite database. Be careful with syntax.")
    query = st.text_area("SQL", value="SELECT name FROM sqlite_master WHERE type='table';", height=120)

    if st.button("Run Query", key="run_sql"):
        try:
            with storage.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()
                cols = result.keys()
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df, use_container_width=True)
            
            # Store result for AI chat
            st.session_state.last_query_result = df
        except Exception as e:
            st.error(f"Query error: {e}")

with tab2:
    if not ai_available:
        st.warning("⚠️ Gemini AI is not available. Check your API key configuration.")
    else:
        st.caption("Ask questions in plain English and get SQL queries automatically.")
        
        # Get available tables and their schemas
        try:
            with storage.engine.connect() as conn:
                tables_result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
                tables = [row[0] for row in tables_result.fetchall()]
            
            # Get schema for each table
            table_schema = {}
            for table in tables:
                with storage.engine.connect() as conn:
                    schema_result = conn.execute(text(f"PRAGMA table_info({table});"))
                    columns = [row[1] for row in schema_result.fetchall()]
                    table_schema[table] = columns
            
            st.info(f"📊 Available tables: {', '.join(tables)}")
            
            # Natural language input
            nl_question = st.text_area(
                "Ask your question",
                placeholder="e.g., Show me the average price from btc_prices table",
                height=100
            )
            
            col1, col2 = st.columns([1, 4])
            with col1:
                generate_sql = st.button("🤖 Generate SQL", key="generate_sql")
            with col2:
                auto_run = st.checkbox("Auto-run query", value=True)
            
            if generate_sql and nl_question:
                with st.spinner("Generating SQL query..."):
                    try:
                        assistant = get_assistant()
                        generated_sql = assistant.natural_language_to_sql(nl_question, table_schema)
                        
                        st.code(generated_sql, language="sql")
                        
                        if auto_run:
                            try:
                                with storage.engine.connect() as conn:
                                    result = conn.execute(text(generated_sql))
                                    rows = result.fetchall()
                                    cols = result.keys()
                                df = pd.DataFrame(rows, columns=cols)
                                st.success("✅ Query executed successfully!")
                                st.dataframe(df, use_container_width=True)
                                
                                # Store result for AI chat
                                st.session_state.last_query_result = df
                                
                                # Offer insights
                                if st.button("💡 Get AI Insights", key="insights"):
                                    with st.spinner("Analyzing data..."):
                                        insights = assistant.generate_data_insights(df, nl_question)
                                        st.markdown("### Insights")
                                        st.write(insights)
                            except Exception as e:
                                st.error(f"Query execution error: {e}")
                    except Exception as e:
                        st.error(f"AI generation error: {e}")
        except Exception as e:
            st.error(f"Error loading database schema: {e}")

# AI Chat about last result
if ai_available and "last_query_result" in st.session_state:
    st.divider()
    st.subheader("💬 Chat about your data")
    
    chat_question = st.text_input("Ask a question about the results above")
    if st.button("Ask AI", key="ask_ai") and chat_question:
        with st.spinner("Thinking..."):
            try:
                assistant = get_assistant()
                answer = assistant.chat_about_data(
                    chat_question,
                    st.session_state.last_query_result,
                    "Query results from the database"
                )
                st.markdown("### Answer")
                st.write(answer)
            except Exception as e:
                st.error(f"Error: {e}")
