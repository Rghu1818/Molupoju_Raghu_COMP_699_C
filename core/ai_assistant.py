"""
AI Assistant module using Google Gemini for intelligent data analysis and insights.
"""
import google.generativeai as genai
import pandas as pd
from typing import Optional, Dict, Any, List
from .config import GEMINI_API_KEY, logger
import json


class GeminiAssistant:
    """Wrapper for Google Gemini AI to provide intelligent analytics features."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini AI with API key."""
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY in config or pass as parameter.")
        
        try:
            genai.configure(api_key=self.api_key)
            # Use gemini-2.5-flash which has better quota limits
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            logger.info("Gemini AI initialized successfully with gemini-2.5-flash")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI: {e}")
            raise
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response from Gemini."""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return f"Error generating response: {str(e)}"
    
    def natural_language_to_sql(self, question: str, table_schema: Dict[str, List[str]]) -> str:
        """
        Convert natural language question to SQL query.
        
        Args:
            question: User's question in natural language
            table_schema: Dict mapping table names to list of column names
        
        Returns:
            SQL query string
        """
        schema_text = "\n".join([
            f"Table: {table}\nColumns: {', '.join(cols)}"
            for table, cols in table_schema.items()
        ])
        
        prompt = f"""You are a SQL expert. Convert the following natural language question into a valid SQLite query.

Available database schema:
{schema_text}

Question: {question}

Return ONLY the SQL query without any explanation or markdown formatting. The query should be executable as-is."""
        
        try:
            sql = self.generate_response(prompt)
            # Clean up the response
            sql = sql.strip()
            # Remove markdown code blocks if present
            if sql.startswith("```"):
                lines = sql.split("\n")
                sql = "\n".join([l for l in lines if not l.startswith("```")])
            sql = sql.strip()
            return sql
        except Exception as e:
            logger.error(f"Error converting NL to SQL: {e}")
            return f"-- Error: {str(e)}"
    
    def explain_anomalies(self, df: pd.DataFrame, anomaly_column: str, context: str = "") -> str:
        """
        Generate explanation for detected anomalies in data.
        
        Args:
            df: DataFrame containing anomaly data
            anomaly_column: Name of the column with anomalous values
            context: Additional context about the data
        
        Returns:
            Human-readable explanation
        """
        # Get summary statistics
        stats = df[anomaly_column].describe().to_dict()
        sample_data = df.head(10).to_dict('records')
        
        prompt = f"""Analyze the following anomalies detected in a dataset and provide a brief, actionable explanation.

Context: {context if context else 'Time series data analysis'}
Column analyzed: {anomaly_column}

Statistics:
- Mean: {stats.get('mean', 'N/A')}
- Std Dev: {stats.get('std', 'N/A')}
- Min: {stats.get('min', 'N/A')}
- Max: {stats.get('max', 'N/A')}

Sample anomalous records:
{json.dumps(sample_data, indent=2, default=str)}

Provide a concise 2-3 sentence explanation of what these anomalies might indicate and potential causes."""
        
        return self.generate_response(prompt)
    
    def generate_data_insights(self, df: pd.DataFrame, data_description: str = "") -> str:
        """
        Generate insights and patterns from a dataset.
        
        Args:
            df: DataFrame to analyze
            data_description: Description of what the data represents
        
        Returns:
            Key insights and patterns found
        """
        # Get basic info
        summary = {
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "sample": df.head(5).to_dict('records')
        }
        
        # Get numeric column statistics
        numeric_stats = {}
        for col in df.select_dtypes(include=['number']).columns:
            numeric_stats[col] = df[col].describe().to_dict()
        
        prompt = f"""Analyze this dataset and provide 3-5 key insights or patterns.

Dataset description: {data_description if data_description else 'Analytics data'}

Dataset info:
- Rows: {summary['rows']}
- Columns: {', '.join(summary['columns'])}

Numeric column statistics:
{json.dumps(numeric_stats, indent=2, default=str)}

Sample data (first 5 rows):
{json.dumps(summary['sample'], indent=2, default=str)}

Provide concise, actionable insights in bullet points."""
        
        return self.generate_response(prompt)
    
    def suggest_alert_rules(self, df: pd.DataFrame, table_name: str) -> str:
        """
        Suggest appropriate alert rules based on data characteristics.
        
        Args:
            df: DataFrame to analyze
            table_name: Name of the table
        
        Returns:
            Suggested alert rules
        """
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        stats = {}
        for col in numeric_cols[:5]:  # Limit to first 5 numeric columns
            stats[col] = {
                'mean': float(df[col].mean()),
                'std': float(df[col].std()),
                'min': float(df[col].min()),
                'max': float(df[col].max())
            }
        
        prompt = f"""Based on the following data characteristics, suggest 2-3 practical alert rules for monitoring.

Table: {table_name}
Numeric columns and their statistics:
{json.dumps(stats, indent=2)}

For each suggested alert, specify:
1. Column to monitor
2. Operator (>, <, >=, <=)
3. Threshold value
4. Brief reason

Format as a simple list."""
        
        return self.generate_response(prompt)
    
    def chat_about_data(self, question: str, df: pd.DataFrame, context: str = "") -> str:
        """
        Answer questions about a specific dataset.
        
        Args:
            question: User's question
            df: DataFrame being discussed
            context: Additional context
        
        Returns:
            Answer to the question
        """
        summary = {
            "shape": df.shape,
            "columns": list(df.columns),
            "head": df.head(3).to_dict('records'),
            "describe": df.describe().to_dict() if not df.empty else {}
        }
        
        prompt = f"""Answer the following question about this dataset.

Context: {context}

Dataset summary:
- Shape: {summary['shape'][0]} rows × {summary['shape'][1]} columns
- Columns: {', '.join(summary['columns'])}

Sample data:
{json.dumps(summary['head'], indent=2, default=str)}

Question: {question}

Provide a clear, concise answer based on the data provided."""
        
        return self.generate_response(prompt)


# Singleton instance
_assistant_instance: Optional[GeminiAssistant] = None


def get_assistant() -> GeminiAssistant:
    """Get or create the singleton Gemini assistant instance."""
    global _assistant_instance
    if _assistant_instance is None:
        _assistant_instance = GeminiAssistant()
    return _assistant_instance


def is_gemini_available() -> bool:
    """Check if Gemini AI is properly configured and available."""
    try:
        get_assistant()
        return True
    except Exception:
        return False
