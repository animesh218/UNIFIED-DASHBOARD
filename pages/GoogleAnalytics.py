import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import base64
from io import BytesIO
from matplotlib.backends.backend_pdf import PdfPages

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'  # Path to your service account file
property_id = '284938146'  # Your GA4 property ID
def get_analytics_client(service_account_file):
    """Create a GA4 Analytics Data API client with service account credentials."""
    try:
        credentials = Credentials.from_service_account_file(
            service_account_file, 
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        return build('analyticsdata', 'v1beta', credentials=credentials)
    except Exception as e:
        st.error(f"Error creating analytics client: {e}")
        return None

def get_ga4_data(service, property_id, start_date, end_date):
    """Query GA4 data with more robust error handling."""
    try:
        # Define core metrics that should always work with GA4
        metrics = [
            {'name': 'totalUsers'},
            {'name': 'activeUsers'},
            {'name': 'newUsers'},
            {'name': 'userEngagementDuration'},
            {'name': 'engagementRate'},
            {'name': 'averageSessionDuration'},
            {'name': 'bounceRate'},
            {'name': 'screenPageViews'},
            {'name': 'sessions'}
        ]
        
        # Try to execute with all metrics
        try:
            return service.properties().runReport(
                property=f"properties/{property_id}",
                body={
                    'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                    'metrics': metrics,
                    'dimensions': [
                        {'name': 'date'}
                    ]
                }
            ).execute()
        except Exception as metric_error:
            # If that fails, fall back to just the core metrics
            st.warning(f"Some advanced metrics may not be available. Using core metrics only. Error: {metric_error}")
            return service.properties().runReport(
                property=f"properties/{property_id}",
                body={
                    'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                    'metrics': [
                        {'name': 'totalUsers'},
                        {'name': 'screenPageViews'},
                        {'name': 'bounceRate'},
                        {'name': 'averageSessionDuration'},
                        {'name': 'sessions'}
                    ],
                    'dimensions': [
                        {'name': 'date'}
                    ]
                }
            ).execute()
    except Exception as e:
        st.error(f"Error fetching GA4 data: {e}")
        return None

def get_top_pages(service, property_id, start_date, end_date, limit=10):
    """Get top performing pages."""
    try:
        return service.properties().runReport(
            property=f"properties/{property_id}",
            body={
                'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                'metrics': [
                    {'name': 'screenPageViews'},
                    {'name': 'activeUsers'},
                    {'name': 'engagementRate'},
                    {'name': 'averageSessionDuration'}
                ],
                'dimensions': [
                    {'name': 'pagePath'}
                ],
                'limit': limit,
                'orderBys': [
                    {'metric': {'metricName': 'screenPageViews'}, 'desc': True}
                ]
            }
        ).execute()
    except Exception as e:
        st.error(f"Error fetching top pages: {e}")
        return None

def get_search_data(service, property_id, start_date, end_date):
    """Get search data including impressions, clicks and search terms."""
    try:
        return service.properties().runReport(
            property=f"properties/{property_id}",
            body={
                'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                'metrics': [
                    {'name': 'impressions'},
                    {'name': 'clicks'},
                    {'name': 'organicGoogleSearchImpressions'},
                    {'name': 'organicGoogleSearchClicks'},
                    {'name': 'organicGoogleSearchClickThroughRate'},
                    {'name': 'organicSearches'}
                ],
                'dimensions': [
                    {'name': 'date'}
                ]
            }
        ).execute()
    except Exception as e:
        # If the full search metrics aren't available, try with a subset
        try:
            st.warning("Some search metrics may not be available. Using core search metrics only.")
            return service.properties().runReport(
                property=f"properties/{property_id}",
                body={
                    'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                    'metrics': [
                        {'name': 'organicSearches'},
                        {'name': 'sessions'}
                    ],
                    'dimensions': [
                        {'name': 'date'}
                    ]
                }
            ).execute()
        except Exception as se:
            st.warning(f"Search metrics may not be fully available in your GA4 property: {se}")
            return None

def get_top_keywords(service, property_id, start_date, end_date, limit=10):
    """Get top search keywords/terms."""
    try:
        return service.properties().runReport(
            property=f"properties/{property_id}",
            body={
                'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                'metrics': [
                    {'name': 'sessions'},
                    {'name': 'activeUsers'},
                    {'name': 'engagementRate'}
                ],
                'dimensions': [
                    {'name': 'sessionSource'},
                    {'name': 'sessionMedium'},
                    {'name': 'searchTerm'}
                ],
                'dimensionFilter': {
                    'filter': {
                        'fieldName': 'sessionMedium',
                        'stringFilter': {
                            'matchType': 'EXACT',
                            'value': 'organic'
                        }
                    }
                },
                'limit': limit,
                'orderBys': [
                    {'metric': {'metricName': 'sessions'}, 'desc': True}
                ]
            }
        ).execute()
    except Exception as e:
        # Try a fallback approach for keywords
        try:
            st.warning("Search term data may be limited. Using alternative dimensions.")
            return service.properties().runReport(
                property=f"properties/{property_id}",
                body={
                    'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                    'metrics': [
                        {'name': 'sessions'},
                        {'name': 'activeUsers'}
                    ],
                    'dimensions': [
                        {'name': 'sessionSource'},
                        {'name': 'sessionMedium'}
                    ],
                    'dimensionFilter': {
                        'filter': {
                            'fieldName': 'sessionMedium',
                            'stringFilter': {
                                'matchType': 'EXACT',
                                'value': 'organic'
                            }
                        }
                    },
                    'limit': limit,
                    'orderBys': [
                        {'metric': {'metricName': 'sessions'}, 'desc': True}
                    ]
                }
            ).execute()
        except Exception as se:
            st.warning(f"Keyword data may not be available in your GA4 property: {se}")
            return None

def parse_ga4_response(response):
    """Parse the GA4 API response into a pandas DataFrame with safe handling of missing columns."""
    if not response:
        return pd.DataFrame()
        
    dimension_headers = [header.get('name') for header in response.get('dimensionHeaders', [])]
    metric_headers = [header.get('name') for header in response.get('metricHeaders', [])]
    
    rows = []
    for row in response.get('rows', []):
        dimensions = [dim.get('value') for dim in row.get('dimensionValues', [])]
        metrics = [metric.get('value') for metric in row.get('metricValues', [])]
        rows.append(dimensions + metrics)
    
    if not rows:
        return pd.DataFrame()
        
    columns = dimension_headers + metric_headers
    df = pd.DataFrame(rows, columns=columns)
    
    # Format date column
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], format="%Y%m%d")
        # Format date as yyyy-mm-dd
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        # Sort by date in ascending order
        df = df.sort_values('date')
    
    # Convert numeric columns - only process columns that exist
    numeric_cols = ['totalUsers', 'activeUsers', 'newUsers', 'userEngagementDuration', 
                    'engagementRate', 'averageSessionDuration', 'bounceRate', 
                    'screenPageViews', 'sessions', 'impressions', 'clicks',
                    'organicGoogleSearchImpressions', 'organicGoogleSearchClicks',
                    'organicGoogleSearchClickThroughRate', 'organicSearches']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Add activeUsers if not present (use totalUsers as fallback)
    if 'activeUsers' not in df.columns and 'totalUsers' in df.columns:
        df['activeUsers'] = df['totalUsers']
        
    # Average engagement time per user
    if 'userEngagementDuration' in df.columns and 'totalUsers' in df.columns:
        df['avgEngPerUser'] = df['userEngagementDuration'] / df['totalUsers']
    else:
        # Fallback to averageSessionDuration if available
        if 'averageSessionDuration' in df.columns:
            df['avgEngPerUser'] = df['averageSessionDuration']
        else:
            df['avgEngPerUser'] = 0
    
    # Calculate returning users
    if 'newUsers' in df.columns and 'totalUsers' in df.columns:
        df['returningUsers'] = df['totalUsers'] - df['newUsers']
    else:
        # Estimate returning users as 30% of total if newUsers not available
        if 'totalUsers' in df.columns:
            df['newUsers'] = df['totalUsers'] * 0.7  # Assume 70% new as fallback
            df['returningUsers'] = df['totalUsers'] * 0.3  # Assume 30% returning as fallback
    
    # User stickiness calculation
    if 'activeUsers' in df.columns and 'totalUsers' in df.columns:
        # Simple daily stickiness (DAU/MAU approximation)
        # Using a 28-day rolling window for MAU
        df_temp = df.copy()
        df_temp['date'] = pd.to_datetime(df_temp['date'])
        df_temp = df_temp.sort_values('date')
        rolling_users = df_temp['totalUsers'].rolling(window=min(28, len(df_temp)), min_periods=1).mean()
        df['userStickiness'] = (df_temp['activeUsers'] / rolling_users) * 100
    else:
        df['userStickiness'] = 0
    
    # Ensure all required columns exist
    required_cols = ['totalUsers', 'activeUsers', 'newUsers', 'avgEngPerUser',
                     'userEngagementDuration', 'returningUsers', 'userStickiness',
                     'engagementRate', 'averageSessionDuration', 'bounceRate', 'screenPageViews']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0
    
    # Reorder columns to match the required format
    columns_order = ['date'] + required_cols
    df = df[columns_order]
    
    return df

def parse_top_pages(response):
    """Parse top pages response into a DataFrame."""
    if not response:
        return pd.DataFrame()
        
    dimension_headers = [header.get('name') for header in response.get('dimensionHeaders', [])]
    metric_headers = [header.get('name') for header in response.get('metricHeaders', [])]
    
    rows = []
    for row in response.get('rows', []):
        dimensions = [dim.get('value') for dim in row.get('dimensionValues', [])]
        metrics = [metric.get('value') for metric in row.get('metricValues', [])]
        rows.append(dimensions + metrics)
    
    if not rows:
        return pd.DataFrame()
        
    columns = dimension_headers + metric_headers
    df = pd.DataFrame(rows, columns=columns)
    
    # Convert numeric columns
    for col in metric_headers:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Format engagement rate as percentage
    if 'engagementRate' in df.columns:
        df['engagementRate'] = df['engagementRate'] * 100
    
    # Format duration to readable format
    if 'averageSessionDuration' in df.columns:
        df['durationFormatted'] = df['averageSessionDuration'].apply(format_duration)
    
    return df

def parse_search_data(response):
    """Parse search data response into a DataFrame."""
    if not response:
        return pd.DataFrame()
    
    df = parse_ga4_response(response)
    
    # Add search-related calculated fields if they don't exist
    if 'organicSearches' not in df.columns:
        df['organicSearches'] = 0
    
    if 'impressions' not in df.columns:
        df['impressions'] = 0
    
    if 'clicks' not in df.columns:
        df['clicks'] = 0
    
    if 'organicGoogleSearchImpressions' not in df.columns:
        df['organicGoogleSearchImpressions'] = 0
    
    if 'organicGoogleSearchClicks' not in df.columns:
        df['organicGoogleSearchClicks'] = 0
    
    if 'organicGoogleSearchClickThroughRate' not in df.columns:
        # Calculate CTR if we have impressions and clicks
        if df['organicGoogleSearchImpressions'].sum() > 0:
            df['organicGoogleSearchClickThroughRate'] = (df['organicGoogleSearchClicks'] / df['organicGoogleSearchImpressions']) * 100
        else:
            df['organicGoogleSearchClickThroughRate'] = 0
    else:
        # Format CTR as percentage
        df['organicGoogleSearchClickThroughRate'] = df['organicGoogleSearchClickThroughRate'] * 100
    
    return df

def parse_keywords(response):
    """Parse keywords/search terms response into a DataFrame."""
    if not response:
        return pd.DataFrame()
        
    dimension_headers = [header.get('name') for header in response.get('dimensionHeaders', [])]
    metric_headers = [header.get('name') for header in response.get('metricHeaders', [])]
    
    rows = []
    for row in response.get('rows', []):
        dimensions = [dim.get('value') for dim in row.get('dimensionValues', [])]
        metrics = [metric.get('value') for metric in row.get('metricValues', [])]
        rows.append(dimensions + metrics)
    
    if not rows:
        return pd.DataFrame()
        
    columns = dimension_headers + metric_headers
    df = pd.DataFrame(rows, columns=columns)
    
    # Convert numeric columns
    for col in metric_headers:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Format engagement rate as percentage if present
    if 'engagementRate' in df.columns:
        df['engagementRate'] = df['engagementRate'] * 100
    
    # Handle case where searchTerm isn't available (GA4 privacy)
    if 'searchTerm' not in df.columns:
        df['searchTerm'] = '(not provided)'
    
    # Replace '(not set)' values with more meaningful text
    if 'searchTerm' in df.columns:
        df['searchTerm'] = df['searchTerm'].replace('(not set)', '(not provided)')
    
    return df

def format_duration(seconds):
    """Format duration in seconds to a readable format."""
    minutes, seconds = divmod(float(seconds), 60)
    if minutes < 1:
        return f"{seconds:.1f} sec"
    else:
        return f"{minutes:.0f}m {seconds:.0f}s"

def create_pdf_report(df, search_df, top_pages_df, keywords_df, figures):
    """Create a PDF report with metrics and plots."""
    buffer = BytesIO()
    
    with PdfPages(buffer) as pdf:
        # Create summary page
        plt.figure(figsize=(11, 8.5))
        plt.axis('off')
        plt.text(0.5, 0.95, "Google Analytics Report", ha='center', fontsize=24)
        plt.text(0.5, 0.9, f"Period: {df['date'].iloc[0]} to {df['date'].iloc[-1]}", ha='center', fontsize=16)
        
        # Add summary metrics
        metrics_text = [
            f"Total Users: {int(df['totalUsers'].sum()):,}",
            f"Active Users: {int(df['activeUsers'].sum()):,}",
            f"New Users: {int(df['newUsers'].sum()):,}",
            f"Returning Users: {int(df['returningUsers'].sum()):,}",
            f"Average Engagement Rate: {df['engagementRate'].mean():.2f}%",
            f"Average Bounce Rate: {df['bounceRate'].mean():.2f}%",
            f"Average Session Duration: {format_duration(df['averageSessionDuration'].mean())}",
            f"Total Page Views: {int(df['screenPageViews'].sum()):,}"
        ]
        
        # Add search metrics if available
        if not search_df.empty and 'organicSearches' in search_df.columns:
            search_metrics = [
                f"Total Organic Searches: {int(search_df['organicSearches'].sum()):,}",
            ]
            
            if 'impressions' in search_df.columns and search_df['impressions'].sum() > 0:
                search_metrics.append(f"Total Impressions: {int(search_df['impressions'].sum()):,}")
            
            if 'clicks' in search_df.columns and search_df['clicks'].sum() > 0:
                search_metrics.append(f"Total Clicks: {int(search_df['clicks'].sum()):,}")
            
            if 'organicGoogleSearchClickThroughRate' in search_df.columns:
                search_metrics.append(f"Average CTR: {search_df['organicGoogleSearchClickThroughRate'].mean():.2f}%")
            
            metrics_text.extend(search_metrics)
        
        y_pos = 0.8
        for metric in metrics_text:
            plt.text(0.5, y_pos, metric, ha='center', fontsize=12)
            y_pos -= 0.05
            
        plt.tight_layout()
        pdf.savefig()
        plt.close()
        
        # Add all figures to the PDF
        for fig in figures:
            pdf.savefig(fig)
            plt.close(fig)
        
        # Add top pages table
        if not top_pages_df.empty:
            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.axis('off')
            ax.text(0.5, 0.98, "Top Performing Pages", ha='center', fontsize=16)
            
            # Prepare table data
            display_cols = ['pagePath', 'screenPageViews', 'activeUsers', 'engagementRate']
            col_indices = [top_pages_df.columns.get_loc(col) for col in display_cols if col in top_pages_df.columns]
            
            table_data = top_pages_df.head(10).values
            table_data_display = table_data[:, col_indices]
            
            # Format column names
            table_cols_display = ['Page Path', 'Views', 'Users', 'Eng. Rate (%)']
            
            # Create the table
            table = ax.table(cellText=table_data_display, 
                    colLabels=table_cols_display,
                    loc='center',
                    cellLoc='center')
            
            # Adjust table styling
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.5)
            
            pdf.savefig(fig)
            plt.close(fig)
            
        # Add keywords table
        if not keywords_df.empty:
            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.axis('off')
            ax.text(0.5, 0.98, "Top Search Keywords", ha='center', fontsize=16)
            
            # Prepare keyword table data
            if 'searchTerm' in keywords_df.columns:
                display_cols = ['searchTerm', 'sessions', 'activeUsers']
                if 'engagementRate' in keywords_df.columns:
                    display_cols.append('engagementRate')
                    
                col_indices = [keywords_df.columns.get_loc(col) for col in display_cols if col in keywords_df.columns]
                
                table_data = keywords_df.head(10).values
                table_data_display = table_data[:, col_indices]
                
                # Format column names
                col_names = ['Keyword', 'Sessions', 'Users']
                if 'engagementRate' in keywords_df.columns:
                    col_names.append('Eng. Rate (%)')
                
                # Create the table
                table = ax.table(cellText=table_data_display, 
                        colLabels=col_names,
                        loc='center',
                        cellLoc='center')
                
                # Adjust table styling
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1, 1.5)
            else:
                ax.text(0.5, 0.5, "Keyword data not available (GA4 privacy restrictions)", 
                        ha='center', fontsize=12)
            
            pdf.savefig(fig)
            plt.close(fig)
        
        # Add raw data table
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis('off')
        ax.text(0.5, 0.98, "Raw Data", ha='center', fontsize=16)
        
        # Create table - limit to showing a reasonable number of rows
        table_data = df.head(20).values
        table_cols = df.columns
        
        # Create the table with limited columns for readability
        display_cols = ['date', 'totalUsers', 'activeUsers', 'newUsers', 'returningUsers', 
                        'engagementRate', 'bounceRate', 'screenPageViews']
        col_indices = [df.columns.get_loc(col) for col in display_cols if col in df.columns]
        
        table_data_display = table_data[:, col_indices]
        table_cols_display = [table_cols[i] for i in col_indices]
        
        ax.table(cellText=table_data_display, 
                colLabels=table_cols_display,
                loc='center',
                cellLoc='center')
        
        pdf.savefig(fig)
        plt.close(fig)
    
    buffer.seek(0)
    return buffer

def get_download_link(buffer, filename="google_analytics_report.pdf"):
    """Generate a download link for the PDF report."""
    b64 = base64.b64encode(buffer.read()).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download PDF Report</a>'

def main():
    st.title("Google Analytics Dashboard")
    
    # Configuration sidebar
    st.sidebar.header("Configuration")
    
    # Service account file upload
    uploaded_file = st.sidebar.file_uploader("Upload Service Account JSON file", type=["json"])
    
    # Set service account file path
    service_account_file = SERVICE_ACCOUNT_FILE
    if uploaded_file is not None:
        # Save uploaded file
        with open("temp_service_account.json", "wb") as f:
            f.write(uploaded_file.getbuffer())
        service_account_file = "temp_service_account.json"
        st.sidebar.success("Service account file uploaded successfully!")
    
    # Property ID input
    st.sidebar.header("Property Settings")
    property_id = st.sidebar.text_input("GA4 Property ID", value="284938146")
    
    # Date range selection
    st.sidebar.header("Date Range")
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    start_date = st.sidebar.date_input("Start Date", start_date)
    end_date = st.sidebar.date_input("End Date", end_date)
    
    if start_date > end_date:
        st.error("Error: Start date must be before end date")
        return
    
    # Format dates for GA
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Fetch data when user clicks button
    if st.sidebar.button("Generate Insights"):
        if not os.path.exists(service_account_file):
            st.error(f"Service account file not found: {service_account_file}")
            st.info("Please upload your service account JSON file to continue.")
            return
            
        if not property_id:
            st.error("Please enter a GA4 Property ID.")
            return
            
        try:
            with st.spinner("Fetching data from Google Analytics..."):
                # Create client with service account
                service = get_analytics_client(service_account_file)
                
                if not service:
                    return
                
                # Get GA4 data
                response = get_ga4_data(service, property_id, start_date_str, end_date_str)
                
                if not response:
                    return
                    
                df = parse_ga4_response(response)
                
                if df.empty:
                    st.warning("No data returned from Google Analytics for the selected period.")
                    return
                
                # Get top pages data
                top_pages_response = get_top_pages(service, property_id, start_date_str, end_date_str)
                top_pages_df = parse_top_pages(top_pages_response)
                
                # Get search data
                search_response = get_search_data(service, property_id, start_date_str, end_date_str)
                search_df = parse_search_data(search_response)
                
                # Get keywords data
                keywords_response = get_top_keywords(service, property_id, start_date_str, end_date_str)
                keywords_df = parse_keywords(keywords_response)
                
                # Display available metrics
                available_metrics = df.columns.tolist()
                st.sidebar.subheader("Available Metrics")
                st.sidebar.info(", ".join([m for m in available_metrics if m != 'date']))
                
                # Store figures for PDF export
                figures = []
                
                # Display overview metrics
                st.header("Overview")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Users", f"{int(df['totalUsers'].sum()):,}")
                    st.metric("Total Views", f"{int(df['screenPageViews'].sum()):,}")
                
                with col2:
                    st.metric("Active Users", f"{int(df['activeUsers'].sum()):,}")
                    avg_engagement = df['avgEngPerUser'].mean()
                    st.metric("Avg. Engagement Time/User", format_duration(avg_engagement))
                
                with col3:
                    avg_bounce = df['bounceRate'].mean()
                    st.metric("Avg. Bounce Rate", f"{avg_bounce:.2f}%")
                    avg_stickiness = df['userStickiness'].mean()
                    st.metric("Avg. User Stickiness", f"{avg_stickiness:.2f}%")
                
                # User Metrics Section
                st.header("User Metrics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Active Users", f"{int(df['activeUsers'].sum()):,}")
                
                with col2:
                    st.metric("New Users", f"{int(df['newUsers'].sum()):,}")
                
                with col3:
                    st.metric("Returning Users", f"{int(df['returningUsers'].sum()):,}")
                
                # Search Metrics Section
                st.header("Search Performance")
                
                # Check if we have search data
                if not search_df.empty and any(col in search_df.columns for col in 
                                              ['impressions', 'clicks', 'organicSearches',
                                               'organicGoogleSearchImpressions', 'organicGoogleSearchClicks']):
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Use available metrics, fall back to zeros if not present
                        if 'organicSearches' in search_df.columns:
                            st.metric("Unique Visitors from Search", f"{int(search_df['organicSearches'].sum()):,}")
                        else:
                            st.metric("Unique Visitors from Search", "Not available")
                    
                    with col2:
                        if 'impressions' in search_df.columns and search_df['impressions'].sum() > 0:
                            st.metric("Impressions", f"{int(search_df['impressions'].sum()):,}")
                        elif 'organicGoogleSearchImpressions' in search_df.columns:
                            st.metric("Impressions", f"{int(search_df['organicGoogleSearchImpressions'].sum()):,}")
                        else:
                            st.metric("Impressions", "Not available")
                    
                    with col3:
                        if 'clicks' in search_df.columns and search_df['clicks'].sum() > 0:
                            st.metric("Clicks", f"{int(search_df['clicks'].sum()):,}")
                        elif 'organicGoogleSearchClicks' in search_df.columns:
                            st.metric("Clicks", f"{int(search_df['organicGoogleSearchClicks'].sum()):,}")
                        else:
                            st.metric("Clicks", "Not available")
                
                    # Calculate CTR if possible
                    if ('organicGoogleSearchImpressions' in search_df.columns and 
                        'organicGoogleSearchClicks' in search_df.columns and 
                        search_df['organicGoogleSearchImpressions'].sum() > 0):
                        
                        ctr = (search_df['organicGoogleSearchClicks'].sum() / 
                               search_df['organicGoogleSearchImpressions'].sum()) * 100
                        st.metric("Average CTR", f"{ctr:.2f}%")
                    elif 'organicGoogleSearchClickThroughRate' in search_df.columns:
                        avg_ctr = search_df['organicGoogleSearchClickThroughRate'].mean()
                        st.metric("Average CTR", f"{avg_ctr:.2f}%")
                else:
                    st.info("Search metrics not available for this property or time period.")
                
                # Chart section
                st.header("Traffic Trend")
                
                # Create users trend plot
                fig1, ax1 = plt.subplots(figsize=(10, 6))
                ax1.plot(df['date'], df['activeUsers'], marker='o', linewidth=2, label='Active Users')
                ax1.plot(df['date'], df['newUsers'], marker='s', linewidth=2, label='New Users')
                ax1.plot(df['date'], df['returningUsers'], marker='^', linewidth=2, label='Returning Users')
                
                ax1.set_xlabel('Date')
                ax1.set_ylabel('Users')
                ax1.set_title('User Trend Over Time')
                ax1.legend()
                ax1.grid(True, alpha=0.3)
                
                # Rotate x-axis labels for better readability
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Add to figures list for PDF
                figures.append(fig1)
                
                # Display the plot in Streamlit
                st.pyplot(fig1)
                
                # Create engagement metrics plot
                fig2, ax2 = plt.subplots(figsize=(10, 6))
                
                ax2.plot(df['date'], df['engagementRate'], marker='o', linewidth=2, label='Engagement Rate (%)')
                ax2.plot(df['date'], df['bounceRate'], marker='s', linewidth=2, label='Bounce Rate (%)')
                
                ax2.set_xlabel('Date')
                ax2.set_ylabel('Rate (%)')
                ax2.set_title('Engagement Metrics Over Time')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
                
                # Rotate x-axis labels for better readability
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Add to figures list for PDF
                figures.append(fig2)
                
                # Display the plot in Streamlit
                st.pyplot(fig2)
                
                # Create session duration plot
                fig3, ax3 = plt.subplots(figsize=(10, 6))
                
                ax3.plot(df['date'], df['averageSessionDuration'], marker='o', linewidth=2, color='purple')
                
                ax3.set_xlabel('Date')
                ax3.set_ylabel('Duration (seconds)')
                ax3.set_title('Average Session Duration')
                ax3.grid(True, alpha=0.3)
                
                # Rotate x-axis labels for better readability
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Add to figures list for PDF
                figures.append(fig3)
                
                # Display the plot in Streamlit
                st.pyplot(fig3)
                
                # Create page views plot
                fig4, ax4 = plt.subplots(figsize=(10, 6))
                
                ax4.plot(df['date'], df['screenPageViews'], marker='o', linewidth=2, color='green')
                
                ax4.set_xlabel('Date')
                ax4.set_ylabel('Page Views')
                ax4.set_title('Page Views Over Time')
                ax4.grid(True, alpha=0.3)
                
                # Rotate x-axis labels for better readability
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Add to figures list for PDF
                figures.append(fig4)
                
                # Display the plot in Streamlit
                st.pyplot(fig4)
                
                # Create user stickiness plot if available
                if 'userStickiness' in df.columns:
                    fig5, ax5 = plt.subplots(figsize=(10, 6))
                    
                    ax5.plot(df['date'], df['userStickiness'], marker='o', linewidth=2, color='orange')
                    
                    ax5.set_xlabel('Date')
                    ax5.set_ylabel('User Stickiness (%)')
                    ax5.set_title('User Stickiness Over Time (DAU/MAU)')
                    ax5.grid(True, alpha=0.3)
                    
                    # Rotate x-axis labels for better readability
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    
                    # Add to figures list for PDF
                    figures.append(fig5)
                    
                    # Display the plot in Streamlit
                    st.pyplot(fig5)
                
                # Display search trends if available
                if not search_df.empty and any(col in search_df.columns for col in 
                                             ['impressions', 'clicks', 'organicSearches']):
                    
                    st.header("Search Trends")
                    
                    if 'organicSearches' in search_df.columns:
                        fig6, ax6 = plt.subplots(figsize=(10, 6))
                        
                        ax6.plot(search_df['date'], search_df['organicSearches'], 
                                marker='o', linewidth=2, color='blue')
                        
                        ax6.set_xlabel('Date')
                        ax6.set_ylabel('Organic Searches')
                        ax6.set_title('Organic Search Visits Over Time')
                        ax6.grid(True, alpha=0.3)
                        
                        # Rotate x-axis labels for better readability
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        
                        # Add to figures list for PDF
                        figures.append(fig6)
                        
                        # Display the plot in Streamlit
                        st.pyplot(fig6)
                
                # Top Pages Section
                st.header("Top Pages")
                
                if not top_pages_df.empty:
                    # For display purposes, shorten long page paths
                    top_pages_df_display = top_pages_df.copy()
                    if 'pagePath' in top_pages_df_display.columns:
                        top_pages_df_display['pagePath'] = top_pages_df_display['pagePath'].apply(
                            lambda x: x[:50] + '...' if len(x) > 50 else x)
                    
                    st.dataframe(top_pages_df_display.head(10))
                else:
                    st.info("Top pages data not available.")
                
                # Top Keywords Section
                st.header("Top Search Keywords")
                
                if not keywords_df.empty and 'searchTerm' in keywords_df.columns:
                    # Check if we have meaningful data (not just 'not provided')
                    has_keywords = any(term != '(not provided)' for term in keywords_df['searchTerm'])
                    
                    if has_keywords:
                        st.dataframe(keywords_df.head(10))
                    else:
                        st.info("Keyword data is protected by Google's privacy policies and shows as '(not provided)'.")
                else:
                    st.info("Keyword data not available.")
                
                # Generate PDF Report
                st.header("Export Report")
                
                pdf_buffer = create_pdf_report(df, search_df, top_pages_df, keywords_df, figures)
                
                # Create download link
                st.markdown(get_download_link(pdf_buffer), unsafe_allow_html=True)
                
                # Download as CSV option
                st.subheader("Download Raw Data")
                
                csv = df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()  # Convert to base64
                href = f'<a href="data:file/csv;base64,{b64}" download="ga_data.csv">Download CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            import traceback
            st.error(traceback.format_exc())

if __name__ == "__main__":
    main()
