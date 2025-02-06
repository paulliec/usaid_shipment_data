from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import os
import pandas as pd
import requests
import snowflake.connector
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from cryptography.hazmat.primitives import serialization

# Load the private key
with open("rsa_key.p8", "rb") as key:
    p_key = serialization.load_pem_private_key(
        key.read(),
        password=None
    )

# Initialize Snowflake connection
if 'CONN' not in st.session_state or st.session_state.CONN is None:
    st.session_state.CONN = snowflake.connector.connect(
        user='streamlit_service',
        account=st.secrets["SNOWFLAKE_ACCOUNT"],
        private_key=p_key,
        warehouse=st.secrets["SNOWFLAKE_WAREHOUSE"],
        role='SYSADMIN',
        database='CITYINSIGHTS',
        schema='DATA',
        host=st.secrets["SNOWFLAKE_HOST"]
    )

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.suggestions = []
    st.session_state.active_suggestion = None

def send_message() -> Dict[str, Any]:
    """Send the entire conversation to the Snowflake Cortex Analyst API."""
    request_body = {
        "messages": st.session_state.messages,
        "semantic_model_file": f"@{st.secrets['SNOWFLAKE_DATABASE']}.{st.secrets['SNOWFLAKE_SCHEMA']}.{st.secrets['SNOWFLAKE_STAGE']}/{st.secrets['SNOWFLAKE_FILE']}",
    }

    resp = requests.post(
        url=f"https://{st.secrets['SNOWFLAKE_HOST']}/api/v2/cortex/analyst/message",
        json=request_body,
        headers={
            "Authorization": f'Snowflake Token="{st.session_state.CONN.rest.token}"',
            "Content-Type": "application/json",
        },
    )
    request_id = resp.headers.get("X-Snowflake-Request-Id")
    if resp.status_code < 400:
        return {**resp.json(), "request_id": request_id}
    else:
        # Rollback last user message if request failed
        if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
        raise Exception(
            f"Failed request (id: {request_id}) with status {resp.status_code}: {resp.text}"
        )

def process_message(prompt: str) -> None:
    # Append user message
    st.session_state.messages.append(
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    )
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Generating response..."):
            response = send_message()
            request_id = response["request_id"]
            content = response["message"]["content"]
            
            # IMPORTANT: Use "analyst" for the assistant's role as per the second script
            st.session_state.messages.append(
                {"role": "analyst", "content": content, "request_id": request_id}
            )
            display_content(content=content, request_id=request_id)

@st.cache_data
def run_sql(sql: str) -> pd.DataFrame:
    """Use Snowflake connector directly with fetch_pandas_all."""
    with st.session_state.CONN.cursor() as cur:
        cur.execute(sql)
        df = cur.fetch_pandas_all()
    return df

def display_content(
    content: List[Dict[str, Any]],
    request_id: Optional[str] = None,
    message_index: Optional[int] = None,
) -> None:
    message_index = message_index or len(st.session_state.messages)
    if request_id:
        with st.expander("Request ID", expanded=False):
            st.markdown(request_id)
    for item in content:
        if item["type"] == "text":
            st.markdown(item["text"])
        elif item["type"] == "suggestions":
            with st.expander("Suggestions", expanded=True):
                for suggestion_index, suggestion in enumerate(item["suggestions"]):
                    if st.button(suggestion, key=f"{message_index}_{suggestion_index}"):
                        st.session_state.active_suggestion = suggestion
        elif item["type"] == "sql":
            with st.expander("SQL Query", expanded=False):
                st.code(item["statement"], language="sql")
            with st.expander("Results", expanded=True):
                with st.spinner("Running SQL..."):
                    df = run_sql(item["statement"])
                    if len(df.index) > 1:
                        data_tab, line_tab, bar_tab = st.tabs(["Data", "Line Chart", "Bar Chart"])
                        data_tab.dataframe(df)
                        if len(df.columns) > 1:
                            df = df.set_index(df.columns[0])
                        with line_tab:
                            # When displaying line charts, specify columns explicitly
                            if "chart" in item["statement"].lower():
                                try:
                                    # If it's a time series chart
                                    time_cols = [col for col in ['time', 'date', 'month'] if col in df.columns]
                                    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
                                    
                                    if time_cols:  # If we found a time column
                                        st.line_chart(
                                            data=df,
                                            x=time_cols[0],  # Use the first time column found
                                            y=numeric_cols.tolist()
                                        )
                                    else:  # No time columns found
                                        if len(numeric_cols) > 0:
                                            st.line_chart(
                                                data=df,
                                                y=numeric_cols.tolist()
                                            )
                                        else:
                                            st.error("No numeric columns found to plot")
                                    
                                    # Always display the raw data
                                    st.dataframe(df)
                                    
                                except Exception as e:
                                    st.error(f"Error displaying chart: {str(e)}")
                                    st.write("Columns available:", df.columns.tolist())  # Debug info
                                    st.dataframe(df)  # Fall back to showing raw data
                        with bar_tab:
                            st.bar_chart(df)
                    else:
                        st.dataframe(df)

# Page config
st.set_page_config(
    page_title="Cincinnati Reviews Explorer",
    page_icon="🌟",
    layout="wide"
)

# Header
st.title("🏙️ Cincinnati Business Reviews & Sentiment Explorer")
st.markdown("""
Explore Google Places reviews and sentiment analysis from businesses around Cincinnati, Ohio! 
This AI-powered tool helps you analyze customer feedback, sentiment trends, and business insights.
""")

# Sidebar with tips
with st.sidebar:
    st.header("💡 Tips for Better Results")
    st.markdown("""
    - Be specific in your questions
    - Include time periods when relevant
    - Mention "reviews", "sentiment", or "businesses" explicitly
    - The AI works best with clear, direct questions
    
    **Sample Questions:**
    - 🏪 How many businesses are in this dataset?
    - 😊 What's the average sentiment score for Cincinnati restaurants?
    - 📊 Which businesses had the most positive sentiment in 2023?
    - 🔍 Show me businesses with negative sentiment trends
    - ⭐ Which restaurant received the most reviews in 2023?
    - 📅 What time period does this data cover?

    """)
    
    st.divider()
    st.caption("""
    **About Sentiment Scores:** Reviews are analyzed for sentiment on a scale from -1 (very negative) to +1 (very positive).
    Built with Streamlit + Snowflake
    """)

# Initialize connection
if 'CONN' not in st.session_state or st.session_state.CONN is None:
    st.session_state.CONN = st.connection('snowflake')

# Dashboard Section
st.header("📊 Cincinnati Reviews Dashboard")
col1, col2 = st.columns(2)

# Example dashboard metrics and charts
with col1:
    # Quick stats card
    st.subheader("📈 Key Metrics")
    try:
        # Get overall stats
        total_businesses = st.session_state.CONN.cursor().execute("""
            SELECT COUNT(DISTINCT NAME) as total 
            FROM CITYINSIGHTS.DATA.CI_REVIEWS
        """).fetchone()[0]
        
        total_reviews = st.session_state.CONN.cursor().execute("""
            SELECT COUNT(DISTINCT id) as total 
            FROM CITYINSIGHTS.DATA.CI_REVIEWS
        """).fetchone()[0]
        
        avg_sentiment = st.session_state.CONN.cursor().execute("""
            SELECT AVG(sentiment) as avg_score 
            FROM CITYINSIGHTS.DATA.CI_REVIEWS\
        """).fetchone()[0]

        st.metric("Total Businesses", f"{total_businesses:,}")
        st.metric("Total Reviews", f"{total_reviews:,}")
        st.metric("Average Sentiment", f"{avg_sentiment:.2f}")
    except Exception as e:
        st.error(f"Error loading metrics: {str(e)}")

with col2:
    # Sentiment Distribution
    try:
        sentiment_data = st.session_state.CONN.cursor().execute("""
            SELECT 
                CASE 
                    WHEN sentiment < -0.3 THEN 'Negative'
                    WHEN sentiment > 0.3 THEN 'Positive'
                    ELSE 'Neutral'
                END as sentiment_category,
                COUNT(*) as count
            FROM CITYINSIGHTS.DATA.CI_REVIEWS
            GROUP BY 1
            ORDER BY 2 DESC
        """).fetch_pandas_all()
        
        fig = px.pie(sentiment_data, 
                    values='COUNT', 
                    names='SENTIMENT_CATEGORY',
                    title='Review Sentiment Distribution',
                    color_discrete_map={'Positive':'#2ecc71',
                                      'Neutral':'#95a5a6',
                                      'Negative':'#e74c3c'})
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading sentiment chart: {str(e)}")

# Time series chart
try:
    time_data = st.session_state.CONN.cursor().execute("""
        SELECT 
            DATE_TRUNC('month', time) as month,
            AVG(sentiment) as avg_sentiment,
            COUNT(*) as review_count
            FROM CITYINSIGHTS.DATA.CI_REVIEWS
        GROUP BY 1
        ORDER BY 1
    """).fetch_pandas_all()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time_data['MONTH'], 
                            y=time_data['AVG_SENTIMENT'],
                            name='Avg Sentiment'))
    fig.add_trace(go.Bar(x=time_data['MONTH'], 
                        y=time_data['REVIEW_COUNT'],
                        name='Review Count',
                        yaxis='y2'))
    
    fig.update_layout(
        title='Review Volume and Sentiment Over Time',
        yaxis=dict(title='Average Sentiment'),
        yaxis2=dict(title='Review Count', overlaying='y', side='right'),
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"Error loading time series chart: {str(e)}")

# Divider
st.divider()

# AI Query Section
st.header("🤖 Ask Questions About the Data")
st.markdown("""
Use natural language to dig deeper into the data or explore specific aspects not covered in the dashboard above.
""")

# Main input area
# st.text_input(
#     "Ask a question",
#     value="Example: Which restaurants had the most positive reviews in 2023?",
#     key="example_input"
# )

# Keep only the actual input area that's connected to the action
user_input = st.chat_input("Ask a question about Cincinnati businesses")
if user_input:
    process_message(prompt=user_input)

# Re-display conversation
for message_index, message in enumerate(st.session_state.messages):
    # The assistant's messages should now have role "analyst"
    chat_role = "user" if message["role"] == "user" else "assistant"
    with st.chat_message(chat_role):
        display_content(
            content=message["content"],
            request_id=message.get("request_id"),
            message_index=message_index,
        )

if st.session_state.active_suggestion:
    process_message(prompt=st.session_state.active_suggestion)
    st.session_state.active_suggestion = None
