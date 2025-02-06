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
from cryptography.hazmat.backends import default_backend
import numpy as np

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="Global Health Commodity Distribution",
    page_icon="🌍",
    layout="wide"
)

# First, let's modify the JavaScript to be more robust
js = '''
    <script>
        // Function to scroll to top
        function scrollToTop() {
            window.parent.document.querySelector(".main").scrollTo(0, 0);
        }
        
        // Call immediately and after a short delay to ensure it works after full page load
        scrollToTop();
        setTimeout(scrollToTop, 100);
    </script>
'''
st.components.v1.html(js)

# Initialize Snowflake connection - remove debug messages
if 'CONN' not in st.session_state or st.session_state.CONN is None:
    try:
        p_key = serialization.load_pem_private_key(
            st.secrets["SNOWFLAKE_PRIVATE_KEY"].encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        st.session_state.CONN = snowflake.connector.connect(
            user=st.secrets["SNOWFLAKE_USER"],
            account=st.secrets["SNOWFLAKE_ACCOUNT"],
            private_key=p_key,
            warehouse=st.secrets["SNOWFLAKE_WAREHOUSE"],
            role=st.secrets["SNOWFLAKE_ROLE"],
            database=st.secrets["SNOWFLAKE_DATABASE"],
            schema=st.secrets["SNOWFLAKE_SCHEMA"]
        )
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {str(e)}")
        raise e

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

    try:
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
            response_data = resp.json()
            
            # If there's SQL in the response, ensure dates are properly formatted
            if "message" in response_data and "content" in response_data["message"]:
                for item in response_data["message"]["content"]:
                    if item.get("type") == "sql":
                        # Convert date formats in SQL
                        item["statement"] = item["statement"].replace(
                            "MM-DD-YYYY", 
                            "YYYY-MM-DD"
                        )
                        
            return {**response_data, "request_id": request_id}
        else:
            # Rollback last user message if request failed
            if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
                st.session_state.messages.pop()
            raise Exception(
                f"Failed request (id: {request_id}) with status {resp.status_code}: {resp.text}"
            )
    except Exception as e:
        st.error(f"Error in send_message: {str(e)}")
        raise e

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
    try:
        # Convert any date literals to ISO format
        sql = sql.replace("'MM-DD-YYYY'", "'YYYY-MM-DD'")
        
        with st.session_state.CONN.cursor() as cur:
            cur.execute(sql)
            df = cur.fetch_pandas_all()
        return df
    except Exception as e:
        st.error(f"SQL Error: {str(e)}")
        st.error(f"Problematic SQL: {sql}")
        raise e

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
                        
                        # Get numeric columns only
                        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
                        
                        if len(df.columns) > 1:
                            df = df.set_index(df.columns[0])
                        
                        with line_tab:
                            try:
                                # If it's a time series chart
                                time_cols = [col for col in df.columns if any(time_word in col.lower() for time_word in ['time', 'date', 'year', 'month'])]
                                
                                if time_cols and numeric_cols:  # If we found both time and numeric columns
                                    st.line_chart(
                                        data=df,
                                        x=time_cols[0],
                                        y=numeric_cols
                                    )
                                elif numeric_cols:  # If we only found numeric columns
                                    st.line_chart(
                                        data=df[numeric_cols]
                                    )
                                else:
                                    st.error("No numeric columns found to plot")
                                
                            except Exception as e:
                                st.error(f"Error displaying line chart: {str(e)}")
                                st.write("Available columns:", df.columns.tolist())
                                st.write("Numeric columns:", numeric_cols)
                        
                        with bar_tab:
                            try:
                                if numeric_cols:
                                    st.bar_chart(
                                        data=df[numeric_cols]
                                    )
                                else:
                                    st.error("No numeric columns found to plot")
                            except Exception as e:
                                st.error(f"Error displaying bar chart: {str(e)}")
                                st.write("Available columns:", df.columns.tolist())
                                st.write("Numeric columns:", numeric_cols)
                    else:
                        st.dataframe(df)

# Header
st.title("🌍 Global Health Commodity Distribution Dashboard")
st.markdown("""
This dashboard highlights the shipments of humanitarian aid and medical supplies distributed globally. 
Each shipment represents lives impacted and communities supported through essential health services.
""")

# Add dataset information
with st.expander("ℹ️ About the Dataset", expanded=False):
    st.markdown("""
    This dataset tracks USAID's global health commodity shipments and deliveries across multiple countries. 
    It was published as part of USAID's commitment to transparency in humanitarian aid distribution.
    
    **Key Information:**
    - Tracks shipments of medical supplies and humanitarian aid
    - Covers multiple health elements including maternal health, malaria prevention, and family planning
    - Provides detailed timeline of deliveries to recipient countries
    - Includes key attributes such as health programs, delivery dates, and recipient countries
    
    The data helps visualize the impact and reach of USAID's global health initiatives and supply chain operations.
    """)

# Filters
# Get years for checkboxes
years_query = """
    SELECT DISTINCT LATEST_ACTUAL_DELIVERY_DATE_YEAR AS YEAR 
    FROM HCD 
    WHERE LATEST_ACTUAL_DELIVERY_DATE_YEAR IS NOT NULL 
    ORDER BY YEAR DESC
"""
years = run_sql(years_query)['YEAR'].tolist()
years = [int(year) for year in years]

# Get unique health elements and countries
health_elements = run_sql("""
    SELECT DISTINCT D365_HEALTH_ELEMENT 
    FROM HCD 
    WHERE D365_HEALTH_ELEMENT NOT IN ('HIV', 'Population TO3', '311Mission', 'Tuberculosis') 
    ORDER BY D365_HEALTH_ELEMENT
""")['D365_HEALTH_ELEMENT'].tolist()
health_elements = ['All'] + health_elements

countries = run_sql("""
    SELECT DISTINCT COUNTRY 
    FROM HCD 
    ORDER BY COUNTRY
""")['COUNTRY'].tolist()
countries = ['All'] + countries

# Create three columns for filters
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    st.write("Select Years")
    # Create a container for the checkboxes with a max height and scrollbar
    with st.container():
        all_years = st.checkbox("All Years", value=True)
        if not all_years:
            selected_years = []
            # Create checkboxes in the container with scrolling
            for year in years:
                if st.checkbox(str(year), key=f"year_{year}"):
                    selected_years.append(year)
            # If no years selected, default to all
            if not selected_years:
                all_years = True
        
with filter_col2:
    selected_health_element = st.selectbox(
        "Select Health Element",
        options=health_elements,
        index=0
    )

with filter_col3:
    selected_country = st.selectbox(
        "Select Country",
        options=countries,
        index=0
    )

# Modify the WHERE clauses in queries to handle year selection
if all_years:
    year_filter = "1=1"  # No filter on year if 'All' is selected
else:
    year_filter = f"LATEST_ACTUAL_DELIVERY_DATE_YEAR IN ({','.join(map(str, selected_years))})"

health_element_filter = "" if selected_health_element == 'All' else f"D365_HEALTH_ELEMENT = '{selected_health_element}'"
country_filter = "" if selected_country == 'All' else f"COUNTRY = '{selected_country}'"

# Key Metrics Row
col1, col2, col3 = st.columns(3)

with col1:
    total_shipments_query = f"""
    SELECT COUNT(*) AS TOTAL_SHIPMENTS 
    FROM HCD 
    WHERE 1=1
    AND {year_filter}
    {' AND ' + health_element_filter if health_element_filter else ''}
    {' AND ' + country_filter if country_filter else ''}
    """
    total_shipments = run_sql(total_shipments_query)['TOTAL_SHIPMENTS'].iloc[0]
    st.metric("Total Shipments", f"{total_shipments:,}")

with col2:
    countries_supported_query = f"""
    SELECT COUNT(DISTINCT COUNTRY) AS COUNTRIES_SUPPORTED 
    FROM HCD 
    WHERE 1=1
    {' AND ' + year_filter if year_filter else ''}
    {' AND ' + health_element_filter if health_element_filter else ''}
    {' AND ' + country_filter if country_filter else ''}
    """
    countries_supported = run_sql(countries_supported_query)['COUNTRIES_SUPPORTED'].iloc[0]
    st.metric("Countries Supported", countries_supported)

with col3:
    year_range_query = f"""
    SELECT 
        MIN(LATEST_ACTUAL_DELIVERY_DATE_YEAR) AS MIN_YEAR,
        MAX(LATEST_ACTUAL_DELIVERY_DATE_YEAR) AS MAX_YEAR
    FROM HCD
    WHERE 1=1
    {' AND ' + year_filter if year_filter else ''}
    {' AND ' + health_element_filter if health_element_filter else ''}
    {' AND ' + country_filter if country_filter else ''}
    """
    year_range = run_sql(year_range_query)
    min_year = int(year_range['MIN_YEAR'].iloc[0])
    max_year = int(year_range['MAX_YEAR'].iloc[0])
    st.metric("Years Covered", f"{min_year}-{max_year}")

# Health Elements Distribution
st.subheader("📊 Shipments by Health Element")
health_elements_query = f"""
SELECT 
    D365_HEALTH_ELEMENT AS HEALTH_ELEMENT, 
    COUNT(*) AS SHIPMENT_COUNT
FROM HCD
WHERE D365_HEALTH_ELEMENT NOT IN ('HIV', 'Population TO3', '311Mission', 'Tuberculosis')
{' AND ' + year_filter if year_filter else ''}
{' AND ' + health_element_filter if health_element_filter else ''}
{' AND ' + country_filter if country_filter else ''}
GROUP BY D365_HEALTH_ELEMENT
ORDER BY SHIPMENT_COUNT ASC
"""
health_elements = run_sql(health_elements_query)
fig = px.bar(health_elements, 
             x='SHIPMENT_COUNT', 
             y='HEALTH_ELEMENT', 
             orientation='h',
             title='Shipments by Health Element',
             labels={'HEALTH_ELEMENT': 'Health Element', 'SHIPMENT_COUNT': 'Number of Shipments'})

# Remove the reversed y-axis setting
fig.update_layout(
    height=400,  # Optional: adjust height if needed
    margin=dict(l=0, r=0, t=30, b=0)  # Optional: adjust margins if needed
)

st.plotly_chart(fig, use_container_width=True)

# Geographic Distribution
st.subheader("🗺️ Geographic Distribution of Shipments")
country_totals_query = f"""
SELECT 
    COUNTRY, 
    COUNT(*) AS SHIPMENT_COUNT,
    COUNT(DISTINCT D365_HEALTH_ELEMENT) as HEALTH_ELEMENTS_COUNT,
    LISTAGG(DISTINCT D365_HEALTH_ELEMENT, ', ') as HEALTH_ELEMENTS
FROM HCD
WHERE 1=1
{' AND ' + year_filter if year_filter else ''}
{' AND ' + health_element_filter if health_element_filter else ''}
{' AND ' + country_filter if country_filter else ''}
AND D365_HEALTH_ELEMENT NOT IN ('HIV', 'Population TO3', '311Mission', 'Tuberculosis')
GROUP BY COUNTRY
"""
country_totals = run_sql(country_totals_query)

fig = px.choropleth(country_totals,
                    locations='COUNTRY',
                    locationmode='country names',
                    color='SHIPMENT_COUNT',
                    hover_name='COUNTRY',
                    hover_data={
                        'SHIPMENT_COUNT': True,
                        'HEALTH_ELEMENTS_COUNT': True,
                        'HEALTH_ELEMENTS': True,
                        'COUNTRY': False
                    },
                    color_continuous_scale='Blues',
                    title=None)

# Make the map more balanced in size and update hover text
fig.update_layout(
    title=None,
    height=500,
    width=None,
    geo=dict(
        showframe=False,
        showcoastlines=True,
        projection_type='equirectangular',
        projection_scale=1.3,
        center=dict(lat=10, lon=20),
        coastlinecolor="Black",
        showland=True,
        landcolor="lightgray",
        showocean=True,
        oceancolor="lightblue",
        showcountries=True,
        countrycolor="Black",
    ),
    hoverlabel=dict(
        bgcolor="white",
        font_size=12,
        font_family="Arial",
        font=dict(
            color="black"  # Make hover text black for better contrast
        )
    ),
    margin=dict(l=0, r=0, t=0, b=0)
)

# Update hover template with darker text
fig.update_traces(
    hovertemplate="<b style='color: black;'>%{hovertext}</b><br>" +
                  "<span style='color: black;'>Shipments: %{z:,}</span><br>" +
                  "<span style='color: black;'>Health Elements: %{customdata[1]}</span><br>" +
                  "<span style='color: black;'>Programs: %{customdata[2]}</span><br>" +
                  "<extra></extra>"
)

# Use container width with the new height
st.plotly_chart(fig, use_container_width=True, height=500)

# Simplified map details
with st.expander("📊 Map Details"):
    st.markdown("""
    - Darker blue indicates more shipments
    - Hover over countries for detailed information
    - Data excludes HIV, Population TO3, 311Mission, and Tuberculosis programs
    """)

# Recent Focus Areas
# Recent Focus Areas
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Top Recipient Countries (Recent Years)")
    recent_country_totals_query = f"""
    SELECT 
        COUNTRY, 
        COUNT(*) AS SHIPMENT_COUNT
    FROM HCD
    WHERE LATEST_ACTUAL_DELIVERY_DATE_YEAR >= 2022
    {' AND ' + health_element_filter if health_element_filter else ''}
    {' AND ' + country_filter if country_filter else ''}
    AND D365_HEALTH_ELEMENT NOT IN ('HIV', 'Population TO3', '311Mission', 'Tuberculosis')
    GROUP BY COUNTRY
    ORDER BY SHIPMENT_COUNT DESC
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
    yearly_health_query = f"""
    SELECT 
        LATEST_ACTUAL_DELIVERY_DATE_YEAR AS DELIVERY_YEAR, 
        D365_HEALTH_ELEMENT AS HEALTH_ELEMENT, 
        COUNT(*) AS SHIPMENT_COUNT
    FROM HCD
    WHERE D365_HEALTH_ELEMENT NOT IN ('HIV', 'Population TO3', '311Mission', 'Tuberculosis')
    {' AND ' + health_element_filter if health_element_filter else ''}
    {' AND ' + country_filter if country_filter else ''}
    GROUP BY LATEST_ACTUAL_DELIVERY_DATE_YEAR, D365_HEALTH_ELEMENT
    ORDER BY LATEST_ACTUAL_DELIVERY_DATE_YEAR
    """
    yearly_health = run_sql(yearly_health_query)
    fig = px.line(yearly_health, 
                  x='DELIVERY_YEAR',
                  y='SHIPMENT_COUNT',
                  color='HEALTH_ELEMENT',
                  title='Shipments Over Time by Health Element',
                  labels={
                      'DELIVERY_YEAR': 'Year',
                      'SHIPMENT_COUNT': 'Count of Shipments',
                      'HEALTH_ELEMENT': 'Health Element'
                  })
    
    # Optional: Update layout for better readability
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Count of Shipments",
        legend_title="Health Element"
    )
    
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

# Create a key in session state for tracking if we've processed the current input
if "current_input_processed" not in st.session_state:
    st.session_state.current_input_processed = False

# Process new input only if we haven't processed it yet
if user_input and not st.session_state.current_input_processed:
    process_message(prompt=user_input)
    st.session_state.current_input_processed = True
    st.session_state.active_suggestion = None  # Clear any active suggestions

# Handle suggestions
if st.session_state.active_suggestion and not st.session_state.current_input_processed:
    process_message(prompt=st.session_state.active_suggestion)
    st.session_state.current_input_processed = True
    st.session_state.active_suggestion = None

# Display conversation history
for message_index, message in enumerate(st.session_state.messages):
    chat_role = "user" if message["role"] == "user" else "analyst"
    with st.chat_message(chat_role):
        display_content(
            content=message["content"],
            request_id=message.get("request_id"),
            message_index=message_index,
        )

# Reset the processed flag on rerun
if st.session_state.current_input_processed:
    st.session_state.current_input_processed = False
