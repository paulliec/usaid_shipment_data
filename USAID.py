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
import numpy as np

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
        database='HEALTHCOMMODITYDATASETDB',
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
    
    with st.chat_message("analyst"):
        with st.spinner("Generating response..."):
            response = send_message()
            request_id = response["request_id"]
            content = response["message"]["content"]
            
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
    page_title="Global Health Commodity Distribution",
    page_icon="🌍",
    layout="wide"
)

# Header
st.title("🌍 Global Health Commodity Distribution Dashboard")
st.markdown("""
This dashboard highlights the shipments of humanitarian aid and medical supplies distributed globally. 
Each shipment represents lives impacted and communities supported through essential health services.
""")

# Key Metrics Row
col1, col2, col3 = st.columns(3)

# Fetch and display key metrics
total_shipments_query = "SELECT COUNT(*) AS total_shipments FROM HCD"
total_shipments = run_sql(total_shipments_query)['TOTAL_SHIPMENTS'].iloc[0]
st.metric("Total Shipments", f"{total_shipments:,}")

countries_supported_query = "SELECT COUNT(DISTINCT COUNTRY) AS countries_supported FROM HCD"
countries_supported = run_sql(countries_supported_query)['COUNTRIES_SUPPORTED'].iloc[0]
st.metric("Countries Supported", countries_supported)

latest_year_query = "SELECT MAX(LATEST_ACTUAL_DELIVERY_DATE_YEAR) AS latest_year FROM HCD"
latest_year = run_sql(latest_year_query)['LATEST_YEAR'].iloc[0]
st.metric("Latest Delivery Year", f"{latest_year:.0f}")

# Health Elements Distribution
st.subheader("📊 Shipments by Health Element")
health_elements_query = """
SELECT D365_HEALTH_ELEMENT, COUNT(*) AS shipment_count
FROM HCD
GROUP BY D365_HEALTH_ELEMENT
ORDER BY shipment_count DESC
"""
health_elements = run_sql(health_elements_query)
fig = px.bar(health_elements, 
             x='SHIPMENT_COUNT', 
             y='D365_HEALTH_ELEMENT', 
             orientation='h',
             title='Shipments by Health Element',
             labels={'D365_HEALTH_ELEMENT': 'Health Element', 'SHIPMENT_COUNT': 'Number of Shipments'})
st.plotly_chart(fig, use_container_width=True)

# Geographic Distribution
st.subheader("🗺️ Geographic Distribution of Shipments")
country_totals_query = """
SELECT COUNTRY, COUNT(*) AS shipment_count
FROM HCD
GROUP BY COUNTRY
"""
country_totals = run_sql(country_totals_query)
fig = px.choropleth(country_totals,
                    locations='COUNTRY',
                    locationmode='country names',
                    color='SHIPMENT_COUNT',
                    hover_name='COUNTRY',
                    color_continuous_scale='Viridis',
                    title='Number of Shipments by Country')
st.plotly_chart(fig, use_container_width=True)

# Recent Focus Areas
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Top Recipient Countries (Recent Years)")
    recent_country_totals_query = """
    SELECT COUNTRY, COUNT(*) AS shipment_count
    FROM HCD
    WHERE LATEST_ACTUAL_DELIVERY_DATE_YEAR >= 2022
    GROUP BY COUNTRY
    ORDER BY shipment_count DESC
    LIMIT 10
    """
    recent_country_totals = run_sql(recent_country_totals_query)
    fig = px.bar(recent_country_totals, 
                 x='SHIPMENT_COUNT', 
                 y='COUNTRY', 
                 orientation='h',
                 title='Top Recipients (2022-2023)',
                 labels={'COUNTRY': 'Country', 'SHIPMENT_COUNT': 'Number of Shipments'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🏥 Shipments Over Time by Health Element")
    yearly_health_query = """
    SELECT LATEST_ACTUAL_DELIVERY_DATE_YEAR, D365_HEALTH_ELEMENT, COUNT(*) AS shipment_count
    FROM HCD
    GROUP BY LATEST_ACTUAL_DELIVERY_DATE_YEAR, D365_HEALTH_ELEMENT
    ORDER BY LATEST_ACTUAL_DELIVERY_DATE_YEAR
    """
    yearly_health = run_sql(yearly_health_query)
    fig = px.line(yearly_health, 
                  x='LATEST_ACTUAL_DELIVERY_DATE_YEAR',
                  y='SHIPMENT_COUNT',
                  color='D365_HEALTH_ELEMENT',
                  title='Shipments Over Time by Health Element')
    st.plotly_chart(fig, use_container_width=True)

# Query Section
st.divider()
st.header("🔍 Explore the Data")
st.markdown("""
Use natural language to explore specific aspects of the global health aid distribution.

**Sample Questions:**
- Which countries received the most shipments in 2023?
- Show me the timeline of shipments to Ukraine
- What health elements had the most shipments?
- Which health elements had the highest growth in recent years?
""")

# Main input area for user queries
user_input = st.chat_input("Ask a question about global health shipments")
if user_input:
    process_message(prompt=user_input)

# Re-display conversation
for message_index, message in enumerate(st.session_state.messages):
    chat_role = "user" if message["role"] == "user" else "analyst"
    with st.chat_message(chat_role):
        display_content(
            content=message["content"],
            request_id=message.get("request_id"),
            message_index=message_index,
        )

if st.session_state.active_suggestion:
    process_message(prompt=st.session_state.active_suggestion)
    st.session_state.active_suggestion = None
