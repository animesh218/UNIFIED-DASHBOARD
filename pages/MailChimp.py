import requests
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import altair as alt
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.error("Please login to access this page.")
    st.stop()
    
# Set page configuration
st.set_page_config(layout="wide", page_title="MailChimp Analytics Dashboard")

# MailChimp API Configuration from environment variables
MAILCHIMP_API_KEY = os.getenv("MAILCHIMP_API_KEY")
MAILCHIMP_SERVER_PREFIX = os.getenv("MAILCHIMP_SERVER_PREFIX", "us6")  # Default to us6 if not specified
MAILCHIMP_LIST_ID = os.getenv("MAILCHIMP_LIST_ID")

# Check if environment variables are set
if not MAILCHIMP_API_KEY:
    st.error("MAILCHIMP_API_KEY not found in environment variables. Please set it in your .env file.")
    st.stop()

if not MAILCHIMP_LIST_ID:
    st.error("MAILCHIMP_LIST_ID not found in environment variables. Please set it in your .env file.")
    st.stop()

# Headers for API requests
headers = {
    "Authorization": f"Bearer {MAILCHIMP_API_KEY}"
}

def fetch_data(endpoint, key):
    """Fetches all data from a given MailChimp API endpoint using pagination."""
    url = f"https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/{endpoint}"
    params = {"count": 1000, "offset": 0}
    all_data = []
    
    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json().get(key, [])
            all_data.extend(data)
            if len(data) < 1000:
                break
            params["offset"] += 1000
        else:
            st.error(f"Failed to fetch {endpoint}: {response.status_code} - {response.text}")
            break
    
    return all_data

def get_campaigns():
    return fetch_data("campaigns", "campaigns")

def get_reports():
    return fetch_data("reports", "reports")

def get_list_growth_history():
    """Fetches list growth history for trends over time."""
    return fetch_data(f"lists/{MAILCHIMP_LIST_ID}/growth-history", "history")

def get_campaign_audience(campaign_id):
    """Fetches email activity data with actual email addresses and accurate metrics for a specific campaign."""
    # First, get the detailed email activity data which contains subscriber activity
    email_activity_url = f"https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/reports/{campaign_id}/email-activity"
    params = {"count": 1000, "offset": 0, "fields": "emails.email_id,emails.email_address,emails.activity,emails.last_open,emails.opens_count,emails.clicks_count"}
    
    all_email_activity = []
    
    while True:
        response = requests.get(email_activity_url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json().get("emails", [])
            all_email_activity.extend(data)
            if len(data) < 1000:
                break
            params["offset"] += 1000
        else:
            st.error(f"Failed to fetch email activity: {response.status_code} - {response.text}")
            break
    
    # For any email_activity that doesn't have email_address directly, fetch it
    for subscriber in all_email_activity:
        if "email_address" not in subscriber or not subscriber["email_address"]:
            # Extract the subscriber hash from the email_id
            if "email_id" in subscriber:
                # The format is typically 'ListID:SubscriberHash' or just 'SubscriberHash'
                subscriber_hash = subscriber["email_id"].split(":")[-1] if ":" in subscriber["email_id"] else subscriber["email_id"]
                
                # Fetch the subscriber details to get the email address
                subscriber_url = f"https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/lists/{MAILCHIMP_LIST_ID}/members/{subscriber_hash}"
                subscriber_response = requests.get(subscriber_url, headers=headers)
                
                if subscriber_response.status_code == 200:
                    subscriber_data = subscriber_response.json()
                    subscriber["email_address"] = subscriber_data.get("email_address", "Not Available")
                else:
                    subscriber["email_address"] = f"Failed to fetch: {subscriber_response.status_code}"
        
        # Calculate accurate open count
        if "activity" in subscriber:
            # Count opens from activity
            opens = sum(1 for activity in subscriber["activity"] if activity.get("action") == "open")
            subscriber["opens_count"] = opens if opens > 0 else subscriber.get("opens_count", 0)
            
            # Count clicks from activity
            clicks = sum(1 for activity in subscriber["activity"] if activity.get("action") == "click")
            subscriber["clicks_count"] = clicks if clicks > 0 else subscriber.get("clicks_count", 0)
    
    return all_email_activity

def create_merged_dataframe(campaigns, reports):
    """Creates a merged dataframe with campaign and report data."""
    # Create campaign dataframe
    df_campaigns = pd.DataFrame([{ 
        "Campaign ID": c['id'],
        "Campaign Name": c['settings'].get('title', 'Untitled'),
        "Subject Line": c['settings'].get('subject_line', 'No Subject'),
        "Send Date": datetime.strptime(c.get("send_time", "1970-01-01T00:00:00").split('+')[0], "%Y-%m-%dT%H:%M:%S") if c.get("send_time") else pd.NaT,
        "Emails Sent": c.get("emails_sent", 0), 
        "Open Rate": c.get("report_summary", {}).get("open_rate", 0) * 100 if c.get("report_summary") else 0, 
        "Click Rate": c.get("report_summary", {}).get("click_rate", 0) * 100 if c.get("report_summary") else 0,
        "Status": c.get("status", "Unknown")
    } for c in campaigns])
    
    # Create reports dataframe
    df_reports = pd.DataFrame([{ 
        "Campaign ID": r.get('id', 'Unknown'),
        "Campaign Name": r.get('campaign_title', 'Untitled'),
        "Send Date": datetime.strptime(r.get("send_time", "1970-01-01T00:00:00").split('+')[0], "%Y-%m-%dT%H:%M:%S") if r.get("send_time") else pd.NaT,
        "Subscriber Count": r.get('emails_sent', 0),
        "Open Rate": r.get('opens', {}).get('open_rate', 0) * 100 if 'opens' in r else 0,
        "Click Rate": r.get('clicks', {}).get('click_rate', 0) * 100 if 'clicks' in r else 0,
        "Unsubscribe Rate": r.get('unsubscribes', {}).get('unsubscribe_rate', 0) * 100 if 'unsubscribes' in r else 0,
        "Bounce Rate": r.get('bounces', {}).get('bounce_rate', 0) * 100 if 'bounces' in r else 0
    } for r in reports])
    
    # Merge the dataframes on Campaign ID
    if not df_campaigns.empty and not df_reports.empty:
        merged_df = pd.merge(
            df_campaigns, 
            df_reports, 
            on='Campaign ID', 
            how='outer', 
            suffixes=('_campaign', '_report')
        )
        
        # Combine and clean up columns
        merged_df['Campaign Name'] = merged_df['Campaign Name_campaign'].combine_first(merged_df['Campaign Name_report'])
        merged_df['Send Date'] = merged_df['Send Date_campaign'].combine_first(merged_df['Send Date_report'])
        merged_df['Open Rate'] = merged_df['Open Rate_campaign'].combine_first(merged_df['Open Rate_report'])
        merged_df['Click Rate'] = merged_df['Click Rate_campaign'].combine_first(merged_df['Click Rate_report'])
        merged_df['Emails Sent'] = merged_df['Emails Sent'].combine_first(merged_df['Subscriber Count'])
        
        # Drop redundant columns
        merged_df = merged_df.drop(columns=[
            'Campaign Name_campaign', 'Campaign Name_report', 
            'Send Date_campaign', 'Send Date_report',
            'Open Rate_campaign', 'Open Rate_report',
            'Click Rate_campaign', 'Click Rate_report',
            'Subscriber Count'
        ])
        
        # Format date for display (dd-mm-yyyy format)
        merged_df['Send Date_Original'] = merged_df['Send Date']
        merged_df['Send Date'] = merged_df['Send Date'].dt.strftime('%d-%m-%Y')
        
        # Round percentage columns
        percentage_cols = ['Open Rate', 'Click Rate', 'Unsubscribe Rate', 'Bounce Rate']
        for col in percentage_cols:
            if col in merged_df.columns:
                merged_df[col] = merged_df[col].round(2)
        
        return merged_df
    
    # If one of the dataframes is empty, return the non-empty one
    if not df_campaigns.empty:
        df_campaigns['Send Date_Original'] = df_campaigns['Send Date']
        df_campaigns['Send Date'] = df_campaigns['Send Date'].dt.strftime('%d-%m-%Y')
        return df_campaigns
    elif not df_reports.empty:
        df_reports['Send Date_Original'] = df_reports['Send Date']
        df_reports['Send Date'] = df_reports['Send Date'].dt.strftime('%d-%m-%Y')
        return df_reports
    else:
        return pd.DataFrame()

def plot_campaign_performance(df, date_range=None):
    """Creates a simplified plot of campaign performance over time."""
    if df.empty or 'Send Date_Original' not in df.columns:
        return None
    
    df_plot = df.copy()
    
    # Filter by date range if provided
    if date_range:
        mask = (df_plot['Send Date_Original'] >= date_range[0]) & (df_plot['Send Date_Original'] <= date_range[1])
        df_plot = df_plot[mask]
    
    # Sort by send date
    df_plot = df_plot.sort_values('Send Date_Original')
    
    # Create a simpler chart with minimal styling
    base = alt.Chart(df_plot).encode(
        x=alt.X('Send Date_Original:T', 
                title='Send Date',
                axis=alt.Axis(format='%d-%m-%Y', labelAngle=-45))
    )
    
    # Line chart for Open Rate
    open_line = base.mark_line(point=True, color='blue').encode(
        y=alt.Y('Open Rate:Q', title='Rate (%)'),
        tooltip=['Campaign Name', alt.Tooltip('Send Date_Original:T', format='%d-%m-%Y'), 'Open Rate']
    )
    
    # Line chart for Click Rate
    click_line = base.mark_line(point=True, color='green').encode(
        y=alt.Y('Click Rate:Q'),
        tooltip=['Campaign Name', alt.Tooltip('Send Date_Original:T', format='%d-%m-%Y'), 'Click Rate']
    )
    
    # Combine the charts
    chart = alt.layer(
        open_line, 
        click_line
    ).properties(
        title='Campaign Performance Trends',
        width=700,
        height=400
    ).resolve_scale(
        y='shared'
    )
    
    # Add a simple legend
    legend = alt.Chart(pd.DataFrame({
        'Metric': ['Open Rate', 'Click Rate'],
        'Color': ['blue', 'green'],
        'Value': [0, 0]  # placeholder
    })).mark_point().encode(
        y=alt.Y('Value:Q', title=None, axis=alt.Axis(labels=False, ticks=False)),
        x=alt.X('Metric:N', title=None),
        color=alt.Color('Color:N', scale=None)
    ).properties(
        width=80,
        height=50
    )
    
    return chart

def plot_subscriber_growth(growth_history, date_range=None):
    """Creates a simplified subscriber growth chart."""
    if not growth_history:
        return None
    
    growth_df = pd.DataFrame([{
        "Month": datetime.strptime(h.get('month', '1970-01'), '%Y-%m'),
        "Subscriber Count": h.get('existing', 0),
        "New Subscribers": h.get('imports', 0) + h.get('optins', 0),
        "Unsubscribes": h.get('unsubscribes', 0),
        "Net Growth": (h.get('imports', 0) + h.get('optins', 0)) - h.get('unsubscribes', 0)
    } for h in growth_history])
    
    growth_df = growth_df.sort_values('Month')
    
    # Filter by date range if provided
    if date_range:
        start_month = date_range[0].replace(day=1)
        end_month = (date_range[1].replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        mask = (growth_df['Month'] >= start_month) & (growth_df['Month'] <= end_month)
        growth_df = growth_df[mask]
    
    # Format month for display
    growth_df['Month_Display'] = growth_df['Month'].dt.strftime('%m-%Y')
    
    # Create a simple area chart for subscriber count
    area_chart = alt.Chart(growth_df).mark_area(
        opacity=0.5,
        color='blue'
    ).encode(
        x=alt.X('Month:T', title='Month', axis=alt.Axis(format='%m-%Y')),
        y=alt.Y('Subscriber Count:Q', title='Subscribers'),
        tooltip=['Month_Display', 'Subscriber Count', 'New Subscribers', 'Unsubscribes']
    ).properties(
        title='Subscriber Growth',
        width=700,
        height=300
    )
    
    return area_chart

def filter_dataframe_by_date(df, start_date, end_date):
    """Filter dataframe by date range."""
    if 'Send Date_Original' not in df.columns:
        return df
    
    mask = (df['Send Date_Original'] >= start_date) & (df['Send Date_Original'] <= end_date)
    return df[mask]

# Streamlit Dashboard
st.title("📊 MailChimp Unified Dashboard")

# Display configuration information in sidebar
st.sidebar.header("Configuration")
if MAILCHIMP_API_KEY and MAILCHIMP_LIST_ID:
    st.sidebar.success("✅ MailChimp API credentials loaded")
    st.sidebar.info(f"Server: {MAILCHIMP_SERVER_PREFIX}")
else:
    st.sidebar.error("❌ MailChimp API credentials missing")
    st.sidebar.info("Create a .env file in the same directory with the following variables:\n\nMAILCHIMP_API_KEY=your_api_key\nMAILCHIMP_SERVER_PREFIX=your_server_prefix\nMAILCHIMP_LIST_ID=your_list_id")

# Date Range Filter
st.sidebar.header("Date Range Filter")
today = datetime.now()
default_start = today - timedelta(days=180)  # Default to last 6 months
default_end = today

start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", default_end)

if start_date > end_date:
    st.sidebar.error("Error: End date must be after start date")
    date_range_valid = False
else:
    date_range_valid = True
    date_range = (datetime.combine(start_date, datetime.min.time()), 
                  datetime.combine(end_date, datetime.max.time()))

# Fetch Data Button
if st.sidebar.button("Fetch MailChimp Data"):
    if date_range_valid:
        if not MAILCHIMP_API_KEY or not MAILCHIMP_LIST_ID:
            st.error("Missing MailChimp API credentials. Please check your .env file.")
        else:
            # Fetch all data
            with st.spinner("Fetching data from MailChimp..."):
                campaigns = get_campaigns()
                reports = get_reports()
                growth_history = get_list_growth_history()

            # Create merged dataframe
            merged_df = create_merged_dataframe(campaigns, reports)
            
            # Filter by date range
            if not merged_df.empty:
                filtered_df = filter_dataframe_by_date(merged_df, date_range[0], date_range[1])
                st.session_state['merged_df'] = merged_df
                st.session_state['filtered_df'] = filtered_df
                st.session_state['growth_history'] = growth_history
                st.session_state['campaigns'] = campaigns
                st.session_state['data_loaded'] = True
            else:
                st.error("No data retrieved from MailChimp")
                st.session_state['data_loaded'] = False
    else:
        st.error("Please fix the date range")

# Initialize session state if not exists
if 'data_loaded' not in st.session_state:
    st.session_state['data_loaded'] = False

# Dashboard layout with tabs (only show if data is loaded)
if st.session_state.get('data_loaded', False):
    tab1, tab2, tab3, tab4 = st.tabs(["📑 Overview", "📈 Trends", "🔍 Audience", "🏆 Top Performers"])
    
    merged_df = st.session_state['merged_df']
    filtered_df = st.session_state['filtered_df']
    growth_history = st.session_state['growth_history']
    campaigns = st.session_state['campaigns']
    
    with tab1:
        st.header("Campaign Overview")
        
        # Display date range info
        st.info(f"Showing data from {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}")
        
        # Summary metrics
        if not filtered_df.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                campaign_count = len(filtered_df)
                st.metric("Total Campaigns", campaign_count)
            
            with col2:
                avg_open_rate = filtered_df['Open Rate'].mean()
                st.metric("Avg Open Rate", f"{avg_open_rate:.2f}%")
            
            with col3:
                avg_click_rate = filtered_df['Click Rate'].mean()
                st.metric("Avg Click Rate", f"{avg_click_rate:.2f}%")
            
            with col4:
                total_emails = filtered_df['Emails Sent'].sum()
                st.metric("Total Emails", f"{total_emails:,}")
        
        # Display filtered dataframe
        if not filtered_df.empty:
            st.subheader("Campaign List")
            st.dataframe(filtered_df.sort_values('Send Date_Original', ascending=False), use_container_width=True)
            st.download_button(
                "Download Report", 
                filtered_df.to_csv(index=False), 
                "mailchimp_report.csv", 
                "text/csv"
            )
        else:
            st.info("No campaigns found in the selected date range.")
    
    with tab2:
        st.header("Performance Trends")
        
        # Simplified campaign performance chart
        if not filtered_df.empty:
            st.subheader("Campaign Performance")
            campaign_chart = plot_campaign_performance(filtered_df, date_range)
            if campaign_chart:
                st.altair_chart(campaign_chart, use_container_width=True)
            
            # Simplified subscriber growth chart
            st.subheader("Subscriber Growth")
            subscriber_chart = plot_subscriber_growth(growth_history, date_range)
            if subscriber_chart:
                st.altair_chart(subscriber_chart, use_container_width=True)
        else:
            st.info("No data available for the selected date range.")
    
    with tab3:
        st.header("Audience Details")
        
        # Campaign selector (filtered by date range)
        if campaigns:
            # Filter campaigns by date range
            date_filtered_campaigns = []
            for c in campaigns:
                if c.get("send_time"):
                    send_date = datetime.strptime(c.get("send_time", "1970-01-01T00:00:00").split('+')[0], "%Y-%m-%dT%H:%M:%S")
                    if date_range[0] <= send_date <= date_range[1]:
                        date_filtered_campaigns.append(c)
                
            if date_filtered_campaigns:
                campaign_options = {c['id']: f"{c['settings']['title']} ({datetime.strptime(c.get('send_time', '1970-01-01').split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%d-%m-%Y')})" 
                                  for c in date_filtered_campaigns if 'settings' in c and 'title' in c['settings']}
                
                selected_campaign = st.selectbox("Select a Campaign", options=list(campaign_options.keys()), 
                                              format_func=lambda x: campaign_options.get(x, "Unknown"))
                
                selected_campaign_data = next((c for c in campaigns if c['id'] == selected_campaign), None)
                if selected_campaign_data:
                    # Campaign details
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Emails Sent", selected_campaign_data.get('emails_sent', 'N/A'))
                    with col2:
                        st.metric("Open Rate", f"{round(selected_campaign_data.get('report_summary', {}).get('open_rate', 0) * 100, 2)}%" if selected_campaign_data.get('report_summary') else 'N/A')
                    with col3:
                        st.metric("Click Rate", f"{round(selected_campaign_data.get('report_summary', {}).get('click_rate', 0) * 100, 2)}%" if selected_campaign_data.get('report_summary') else 'N/A')
                    
                    # Show loading indicator for audience data
                    with st.spinner("Fetching audience data... This may take a moment."):
                        audience_data = get_campaign_audience(selected_campaign)
                    
                    if audience_data:
                        # Create audience dataframe
                        df_audience = pd.DataFrame([{ 
                            "Email Address": a.get("email_address", "N/A"),
                            "Open Count": a.get("opens_count", 0),
                            "Click Count": a.get("clicks_count", 0),
                            "Last Opened": datetime.strptime(a.get("last_open", "1970-01-01T00:00:00").split('+')[0], "%Y-%m-%dT%H:%M:%S").strftime("%d-%m-%Y %H:%M") if a.get("last_open") else "N/A" 
                        } for a in audience_data])
                        
                        # Display simplified audience engagement visualization
                        st.subheader("Audience Overview")
                        
                        # Simple bar chart for engagement distribution
                        engagement_data = pd.DataFrame({
                            'Category': ['Never Opened', 'Opened Only', 'Clicked'],
                            'Count': [
                                len(df_audience[df_audience['Open Count'] == 0]),
                                len(df_audience[(df_audience['Open Count'] > 0) & (df_audience['Click Count'] == 0)]),
                                len(df_audience[df_audience['Click Count'] > 0])
                            ]
                        })
                        
                        engagement_chart = alt.Chart(engagement_data).mark_bar().encode(
                            x=alt.X('Category:N', title=None, axis=alt.Axis(labelAngle=0)),
                            y=alt.Y('Count:Q', title='Number of Subscribers'),
                            color=alt.Color('Category:N', scale=alt.Scale(
                                domain=['Never Opened', 'Opened Only', 'Clicked'],
                                range=['#FF9999', '#FFCC99', '#99CC99']
                            )),
                            tooltip=['Category', 'Count']
                        ).properties(
                            title='Engagement Distribution',
                            width=600,
                            height=300
                        )
                        
                        st.altair_chart(engagement_chart, use_container_width=True)
                        
                        # Display audience data table
                        st.subheader("Subscriber Activity")
                        st.dataframe(df_audience, use_container_width=True)
                        st.download_button(
                            "Download Audience Data", 
                            df_audience.to_csv(index=False), 
                            "audience_data.csv", 
                            "text/csv"
                        )
                    else:
                        st.info("No audience data available for this campaign.")
            else:
                st.info("No campaigns available in the selected date range.")
        else:
            st.info("No campaigns available.")
    
    with tab4:
        st.header("Top Performers")
        
        if not filtered_df.empty:
            # Simple top campaigns section
            st.subheader("Best Campaigns")
            
            # Create a simple horizontal bar chart for top campaigns
            top_campaigns = filtered_df.sort_values('Open Rate', ascending=False).head(5)
            
            top_chart = alt.Chart(top_campaigns).mark_bar().encode(
                y=alt.Y('Campaign Name:N', sort='-x', title=None),
                x=alt.X('Open Rate:Q', title='Open Rate (%)'),
                color=alt.Color('Open Rate:Q', scale=alt.Scale(scheme='blues')),
                tooltip=['Campaign Name', 'Send Date', 'Open Rate', 'Click Rate', 'Emails Sent']
            ).properties(
                title='Top 5 Campaigns by Open Rate',
                width=600,
                height=200
            )
            
            st.altair_chart(top_chart, use_container_width=True)
            
            # Display top campaigns table
            st.dataframe(top_campaigns[['Campaign Name', 'Send Date', 'Open Rate', 'Click Rate', 'Emails Sent']], use_container_width=True)
            
            # Monthly performance simplified view
            if 'Send Date_Original' in filtered_df.columns:
                st.subheader("Monthly Performance")
                
                # Extract month from Send Date
                filtered_df['Month'] = filtered_df['Send Date_Original'].dt.strftime('%m-%Y')
                
                # Group by month
                monthly_stats = filtered_df.groupby('Month').agg({
                    'Open Rate': 'mean',
                    'Click Rate': 'mean',
                    'Emails Sent': 'sum',
                    'Campaign ID': 'count'  # Count campaigns per month
                }).reset_index()
                
                # Rename column
                monthly_stats = monthly_stats.rename(columns={'Campaign ID': 'Campaign Count'})
                
                # Create a DataFrame for the chart
                chart_data = pd.melt(
                    monthly_stats, 
                    id_vars=['Month'], 
                    value_vars=['Open Rate', 'Click Rate'],
                    var_name='Metric', 
                    value_name='Rate'
                )
                
                # Simple line chart
                monthly_chart = alt.Chart(chart_data).mark_line(point=True).encode(
                    x=alt.X('Month:N', title=None, sort=None),
                    y=alt.Y('Rate:Q', title='Rate (%)'),
                    color='Metric:N',
                    tooltip=['Month', 'Metric', 'Rate']
                ).properties(
                    title='Monthly Performance Metrics',
                    width=600,
                    height=300
                )
                
                st.altair_chart(monthly_chart, use_container_width=True)
                
                # Display monthly stats table
                monthly_stats = monthly_stats.sort_values('Month')
                st.dataframe(monthly_stats, use_container_width=True)
        else:
            st.info("No campaign data available in the selected date range.")
else:
    # Instructions for first-time users
    st.info("👈 Please set a date range and click 'Fetch MailChimp Data' in the sidebar to get started.")
    
    # Placeholder tabs for preview
    tab1, tab2, tab3, tab4 = st.tabs(["📑 Overview", "📈 Trends", "🔍 Audience", "🏆 Top Performers"])
    
    with tab1:
        st.header("Campaign Overview")
        st.write("Campaign data will appear here after fetching data.")
    
    with tab2:
        st.header("Performance Trends")
        st.write("Performance charts will appear here after fetching data.")
    
    with tab3:
        st.header("Audience Details")
        st.write("Audience metrics will appear here after fetching data.")
    
    with tab4:
        st.header("Top Performers")
        st.write("Top campaign analysis will appear here after fetching data.")