import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Page config
st.set_page_config(
    page_title="Global Health Commodity Distribution",
    page_icon="🌍",
    layout="wide"
)

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv('data/hcd.csv')
    # Convert price and quantity to numeric
    df['ILLUSTRATIVE_PRICE'] = pd.to_numeric(df['ILLUSTRATIVE_PRICE'], errors='coerce')
    df['ORDERED_QUANTITY'] = pd.to_numeric(df['ORDERED_QUANTITY'], errors='coerce')
    # Calculate total value
    df['total_value'] = df['ILLUSTRATIVE_PRICE'] * df['ORDERED_QUANTITY']
    return df

df = load_data()

# Header
st.title("🌍 Global Health Commodity Distribution Dashboard")
st.markdown("""
This dashboard showcases the vital humanitarian aid and medical supplies distributed globally. 
Each shipment represents lives impacted and communities supported through essential health services.
""")

# Key Metrics Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_value = df['total_value'].sum()
    st.metric("Total Aid Value", f"${total_value:,.0f}")

with col2:
    countries_supported = df['COUNTRY'].nunique()
    st.metric("Countries Supported", countries_supported)

with col3:
    total_shipments = len(df)
    st.metric("Total Shipments", f"{total_shipments:,}")

with col4:
    latest_year = df['LATEST_ACTUAL_DELIVERY_DATE_YEAR'].max()
    st.metric("Latest Delivery Year", f"{latest_year:.0f}")

# Health Elements Distribution
st.subheader("📊 Distribution by Health Element")
health_elements = df.groupby('D365_HEALTH_ELEMENT')['total_value'].sum().sort_values(ascending=True)
fig = px.bar(health_elements, 
             orientation='h',
             title='Aid Distribution by Health Element',
             labels={'D365_HEALTH_ELEMENT': 'Health Element', 'total_value': 'Total Value ($)'})
st.plotly_chart(fig, use_container_width=True)

# Geographic Distribution
st.subheader("🗺️ Geographic Distribution of Aid")
country_totals = df.groupby('COUNTRY')['total_value'].sum().reset_index()
fig = px.choropleth(country_totals,
                    locations='COUNTRY',
                    locationmode='country names',
                    color='total_value',
                    hover_name='COUNTRY',
                    color_continuous_scale='Viridis',
                    title='Total Aid Value by Country')
st.plotly_chart(fig, use_container_width=True)

# Recent Focus Areas
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Top Recipient Countries (Recent Years)")
    recent_years = df[df['LATEST_ACTUAL_DELIVERY_DATE_YEAR'] >= 2022]
    recent_country_totals = recent_years.groupby('COUNTRY')['total_value'].sum().sort_values(ascending=True).tail(10)
    fig = px.bar(recent_country_totals, 
                 orientation='h',
                 title='Top Recipients (2022-2023)',
                 labels={'COUNTRY': 'Country', 'total_value': 'Total Value ($)'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🏥 Health Elements Over Time")
    yearly_health = df.groupby(['LATEST_ACTUAL_DELIVERY_DATE_YEAR', 'D365_HEALTH_ELEMENT'])['total_value'].sum().reset_index()
    fig = px.line(yearly_health, 
                  x='LATEST_ACTUAL_DELIVERY_DATE_YEAR',
                  y='total_value',
                  color='D365_HEALTH_ELEMENT',
                  title='Aid Distribution Trends by Health Element')
    st.plotly_chart(fig, use_container_width=True)

# Query Section
st.divider()
st.header("🔍 Explore the Data")
st.markdown("""
Use natural language to explore specific aspects of the global health aid distribution.

**Sample Questions:**
- Which countries received the most HIV/AIDS support in 2023?
- Show me the timeline of aid to Ukraine
- What types of medical supplies were most distributed?
- Which health elements had the highest growth in recent years?
""")

# Keep the existing query functionality here
# [Previous query code remains unchanged]
