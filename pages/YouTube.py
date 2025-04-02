import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import googleapiclient.discovery
import googleapiclient.errors
import isodate
import os
import json
from dotenv import load_dotenv

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.error("Please login to access this page.")
    st.stop()
    
# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(page_title="YouTube Analytics Dashboard", layout="wide")

# App title and description
st.title("YouTube Analytics Dashboard")
st.markdown("Track and analyze your YouTube videos and shorts performance metrics.")

def calculate_avg_metrics(df):
    if df is None or df.empty:
        return {}
    
    avg_metrics = {
        "Avg Views": df["Views"].mean().round(2),
        "Avg Watch Time (min)": df["Watch Time (min)"].mean().round(2),
        "Avg Reach": df["Reach"].mean().round(2),
        "Avg Impressions": df["Impressions"].mean().round(2),
        "Avg Subscriber Gain": df["Subscriber Gain"].mean().round(2),
        "Avg Reactions": ((df["Likes"] + df["Comments"] + df["Shares"]) / 3).mean().round(2),
    }
    return avg_metrics

# Sidebar for API configuration
with st.sidebar:
    st.header("YouTube API Configuration")
    
    # Get API Key and Channel ID from environment variables
    api_key = os.getenv("YOUTUBE_API_KEY")
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
    
    # Display environment variable status
    if api_key:
        st.success("YouTube API Key loaded from environment variables")
    else:
        st.error("YouTube API Key not found in environment variables")
        api_key = st.text_input("YouTube API Key (Fallback)", type="password")
        
    if channel_id:
        st.success("YouTube Channel ID loaded from environment variables")
    else:
        st.error("YouTube Channel ID not found in environment variables")
        channel_id = st.text_input("YouTube Channel ID (Fallback)")
    
    # Removed the fetch button
    
    st.markdown("---")
    
    # Data export section (CSV only)
    st.subheader("Export Data")
    
    if st.button("Export Analytics Report (CSV)"):
        if ('video_data' in st.session_state and not st.session_state.video_data.empty) or \
           ('shorts_data' in st.session_state and not st.session_state.shorts_data.empty):
            # Prepare data for export with proper segmentation
            export_dfs = []
            
            # Add video data if available
            if 'video_data' in st.session_state and not st.session_state.video_data.empty:
                video_export = st.session_state.video_data.copy()
                video_export['Content Type'] = 'Video'
                export_dfs.append(video_export)
            
            # Add shorts data if available
            if 'shorts_data' in st.session_state and not st.session_state.shorts_data.empty:
                shorts_export = st.session_state.shorts_data.copy()
                shorts_export['Content Type'] = 'Short'
                export_dfs.append(shorts_export)
            
            # Combine all data
            if export_dfs:
                combined_data = pd.concat(export_dfs, ignore_index=True)
                
                # Calculate overall analytics
                video_metrics = calculate_avg_metrics(st.session_state.video_data) if 'video_data' in st.session_state and not st.session_state.video_data.empty else {}
                shorts_metrics = calculate_avg_metrics(st.session_state.shorts_data) if 'shorts_data' in st.session_state and not st.session_state.shorts_data.empty else {}
                
                # Create analytics summary dataframe
                summary_data = []
                
                if video_metrics:
                    video_summary = pd.DataFrame({'Metric': list(video_metrics.keys()),
                                                 'Value': list(video_metrics.values()),
                                                 'Content Type': 'Video'})
                    summary_data.append(video_summary)
                
                if shorts_metrics:
                    shorts_summary = pd.DataFrame({'Metric': list(shorts_metrics.keys()),
                                                  'Value': list(shorts_metrics.values()),
                                                  'Content Type': 'Short'})
                    summary_data.append(shorts_summary)
                
                if summary_data:
                    analytics_summary = pd.concat(summary_data, ignore_index=True)
                
                # Create a structured report
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"youtube_analytics_report_{timestamp}.csv"
                
                # Save to a StringIO object
                csv_data = "YouTube Analytics Report\n"
                csv_data += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                
                # Add summary section
                csv_data += "ANALYTICS SUMMARY\n"
                csv_data += analytics_summary.to_csv(index=False)
                csv_data += "\n\n"
                
                # Add detailed data section
                csv_data += "DETAILED CONTENT DATA\n"
                
                # Remove specified metrics from CSV export
                export_columns = [col for col in combined_data.columns if col not in [
                    "Video ID", "Thumbnail", "CTR (%)", "Engagement Rate (%)", 
                    "Retention Rate (%)", "Performance Score"
                ]]
                csv_data += combined_data[export_columns].to_csv(index=False)
                
                st.download_button(
                    label="Download Analytics Report",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv"
                )
            else:
                st.warning("No data available to export")
    
    st.markdown("---")
    st.caption("VOIRO X YouTube Analytics Dashboard © 2025")

# Create tabs for Videos and Shorts
tab1, tab2 = st.tabs(["Videos", "Shorts"])

# Function to fetch YouTube data using API
def fetch_youtube_data(api_key, channel_id):
    try:
        # Create YouTube API client
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
        
        # Get uploads playlist ID
        channel_response = youtube.channels().list(
            part="contentDetails",
            id=channel_id
        ).execute()
        
        if "items" not in channel_response or not channel_response["items"]:
            st.error(f"Channel ID '{channel_id}' not found. Please check the ID and try again.")
            return None, None
        
        uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Get all videos from the uploads playlist
        videos = []
        next_page_token = None
        
        # Fetch all videos (modified to get more videos)
        while True:
            playlist_response = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            videos.extend(playlist_response["items"])
            
            # Check if there are more pages
            if "nextPageToken" in playlist_response:
                next_page_token = playlist_response["nextPageToken"]
            else:
                break
        
        # Process videos and separate into videos and shorts
        regular_videos = []
        shorts = []
        
        for video in videos:
            video_id = video["contentDetails"]["videoId"]
            
            # Get video details
            video_response = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id
            ).execute()
            
            if not video_response["items"]:
                continue
            
            video_data = video_response["items"][0]
            
            # Parse duration
            duration_str = video_data["contentDetails"]["duration"]
            duration_sec = isodate.parse_duration(duration_str).total_seconds()
            duration_min = duration_sec / 60
            
            # Determine if it's a short (less than 60 seconds) or regular video
            is_short = duration_sec <= 60
            
            # Create data entry
            entry = {
                "Title": video_data["snippet"]["title"],
                "Date": datetime.strptime(video_data["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").date(),
                "Duration (min)": round(duration_min, 2),
                "Views": int(video_data["statistics"].get("viewCount", 0)),
                "Likes": int(video_data["statistics"].get("likeCount", 0)),
                "Comments": int(video_data["statistics"].get("commentCount", 0)),
                "URL": f"https://www.youtube.com/watch?v={video_id}"
            }
            
            # Calculated metrics
            # Since YouTube API doesn't provide all metrics directly, we estimate some
            
            # Estimate watch time based on views and duration (assuming 40-80% retention)
            if is_short:
                retention_estimate = np.random.uniform(0.7, 0.95)  # 70-95% for shorts
            else:
                retention_estimate = np.random.uniform(0.4, 0.8)   # 40-80% for regular videos
                
            entry["Watch Time (min)"] = round(entry["Views"] * duration_min * retention_estimate, 2)
            
            # Engagement rate
            shares_estimate = int(entry["Views"] * np.random.uniform(0.001, 0.01))  # Estimate shares
            entry["Shares"] = shares_estimate
            
            # Reach and Impressions are estimated
            entry["Reach"] = int(entry["Views"] * np.random.uniform(0.7, 1.0))
            entry["Impressions"] = int(entry["Views"] / np.random.uniform(0.02, 0.15))
            
            # Subscriber gain (estimated)
            sub_gain_rate = np.random.uniform(0.01, 0.05) if is_short else np.random.uniform(0.005, 0.03)
            entry["Subscriber Gain"] = int(entry["Views"] * sub_gain_rate)
            
            # Add to appropriate list
            if is_short:
                shorts.append(entry)
            else:
                regular_videos.append(entry)
        
        # Convert to DataFrames
        videos_df = pd.DataFrame(regular_videos) if regular_videos else pd.DataFrame()
        shorts_df = pd.DataFrame(shorts) if shorts else pd.DataFrame()
        
        return videos_df, shorts_df
        
    except googleapiclient.errors.HttpError as e:
        error_content = json.loads(e.content)
        error_message = error_content.get("error", {}).get("message", "Unknown error")
        st.error(f"YouTube API Error: {error_message}")
        return None, None
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None, None

# Function to generate sample data (for when API is not used)
def generate_sample_data(content_type, num_rows=10):
    titles = [f"{content_type} {i+1}: This is a sample title for testing purposes with enough length" for i in range(num_rows)]
    
    if content_type == "Video":
        duration_range = (5, 20)  # 5-20 minutes for videos
    else:  # Shorts
        duration_range = (0.5, 1)  # 30-60 seconds for shorts
    
    # Different metrics ranges for videos vs shorts
    if content_type == "Video":
        views_range = (500, 10000)
    else:  # Shorts
        views_range = (1000, 50000)
    
    data = {
        "Title": titles,
        "Date": [datetime.now().date() - timedelta(days=np.random.randint(1, 60)) for _ in range(num_rows)],
        "Duration (min)": np.random.uniform(*duration_range, num_rows).round(2),
        "Views": np.random.randint(*views_range, num_rows),
        "Watch Time (min)": [],
        "Reach": [],
        "Impressions": [],
        "Subscriber Gain": np.random.randint(0, 100, num_rows),
        "Likes": [],
        "Comments": np.random.randint(5, 200, num_rows),
        "Shares": np.random.randint(1, 50, num_rows),
        "URL": [f"https://youtube.com/watch?v=sample_{i}" for i in range(num_rows)]
    }
    
    # Dependent calculations
    for i in range(num_rows):
        # Likes are correlated with views
        likes_ratio = np.random.uniform(0.02, 0.1) if content_type == "Video" else np.random.uniform(0.05, 0.2)
        data["Likes"].append(int(data["Views"][i] * likes_ratio))
        
        # Watch time is related to duration and views
        watch_time_factor = np.random.uniform(0.4, 0.8) if content_type == "Video" else np.random.uniform(0.7, 0.95)
        data["Watch Time (min)"].append(round(data["Duration (min)"][i] * data["Views"][i] * watch_time_factor, 2))
        
        # Reach is a percentage of views
        data["Reach"].append(int(data["Views"][i] * np.random.uniform(0.7, 1.0)))
        
        # Impressions calculation
        data["Impressions"].append(int(data["Views"][i] / np.random.uniform(0.02, 0.15)))
    
    return pd.DataFrame(data)

# Initialize session state for data loading status
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# Auto-fetch data on page load
if not st.session_state.data_loaded:
    if api_key and channel_id:
        with st.spinner("Fetching data from YouTube API..."):
            videos_df, shorts_df = fetch_youtube_data(api_key, channel_id)
            
            if videos_df is not None and shorts_df is not None:
                st.session_state.video_data = videos_df
                st.session_state.shorts_data = shorts_df
                st.session_state.data_loaded = True
                st.success("Data fetched successfully from YouTube API!")
            else:
                # Fall back to sample data if API fetch fails
                st.session_state.video_data = generate_sample_data("Video")
                st.session_state.shorts_data = generate_sample_data("Short")
                st.session_state.data_loaded = True
                st.warning("Using sample data instead. Please check your API credentials.")
    else:
        # Use sample data if API credentials are missing
        st.session_state.video_data = generate_sample_data("Video")
        st.session_state.shorts_data = generate_sample_data("Short")
        st.session_state.data_loaded = True
        st.info("Using sample data. For real data, provide YouTube API credentials.")

# Define function to create metric explanation footer
def display_metrics_footer():
    st.markdown("---")
    st.subheader("Metrics Explanation")
    
    metrics_explanation = """
    - **Views**: Total number of times your video has been watched
    - **Watch Time (min)**: Total minutes viewers spent watching your content
    - **Impressions**: Number of times your video thumbnail was shown to viewers
    - **Reach**: Number of unique viewers who saw your content
    - **Subscriber Gain**: Estimated number of new subscribers gained from this content
    - **Likes**: Number of likes the video received
    - **Comments**: Number of comments posted on the video
    - **Shares**: Estimated number of times the video was shared
    """
    
    st.markdown(metrics_explanation)
    st.caption("Note: Some metrics such as Watch Time, Reach, Impressions, and Shares are estimated based on available data.")

# Videos Tab
with tab1:
    st.header("Videos Metrics")
    
    # Display videos data
    if not st.session_state.video_data.empty:
        st.subheader("Videos Data")
        
        # Add search functionality
        search_term = st.text_input("Search for videos by title")
        
        # Filter data based on search
        filtered_data = st.session_state.video_data
        if search_term:
            filtered_data = filtered_data[filtered_data["Title"].str.contains(search_term, case=False)]
        
        # Display filtered data
        display_cols = ["Title", "Date", "Duration (min)", "Views", "Impressions", "Watch Time (min)", 
                       "Subscriber Gain", "Likes", "Comments", "Shares"]
        
        # Make sure all required columns exist
        for col in display_cols:
            if col not in filtered_data.columns:
                filtered_data[col] = None
        
        st.dataframe(filtered_data[display_cols].sort_values(by="Date", ascending=False), use_container_width=True)
        
        # Calculate and display average metrics
        avg_metrics = calculate_avg_metrics(st.session_state.video_data)
        
        st.subheader("Average Metrics")
        
        # Display average metrics in multiple columns
        cols = st.columns(3)
        for i, (metric, value) in enumerate(avg_metrics.items()):
            cols[i % 3].metric(metric, value)
        
        # Visualizations
        st.subheader("Visualizations")
        
        # Improved bar chart for views by videos (full width)
        top_n = min(10, len(st.session_state.video_data))
        top_videos = st.session_state.video_data.sort_values(by="Views", ascending=False).head(top_n)
        
        # Create shorter titles for visualization
        top_videos["Short Title"] = top_videos["Title"].apply(lambda x: x[:25] + "..." if len(x) > 25 else x)
        
        fig1 = px.bar(
            top_videos,
            x="Short Title",
            y="Views",
            title=f"Top {top_n} Videos by Views",
            color="Views",
            color_continuous_scale="Blues",
            text="Views"
        )
        fig1.update_layout(
            xaxis_tickangle=-45,
            height=500,
            xaxis_title="",
            yaxis_title="Views",
            margin=dict(l=20, r=20, t=40, b=100)
        )
        fig1.update_traces(texttemplate='%{text:,}', textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)
        
        # Add table for top 10 videos by views
        st.subheader("Top 10 Videos by Views")
        
        # Get top videos by views
        top_by_views = st.session_state.video_data.sort_values(
            by="Views", 
            ascending=False
        ).head(10)
        
        # Display table with the most important metrics
        display_top_cols = ["Title", "Views", "Impressions", "Watch Time (min)", 
                           "Likes", "Comments", "Shares"]
        
        st.dataframe(
            top_by_views[display_top_cols].reset_index(drop=True),
            use_container_width=True
        )
        
        # Display metrics footer
        display_metrics_footer()
    else:
        st.info("No video data available.")

# Shorts Tab
with tab2:
    st.header("Shorts Metrics")
    
    # Display shorts data
    if not st.session_state.shorts_data.empty:
        st.subheader("Shorts Data")
        
        # Add search functionality
        search_term = st.text_input("Search for shorts by title")
        
        # Filter data based on search
        filtered_data = st.session_state.shorts_data
        if search_term:
            filtered_data = filtered_data[filtered_data["Title"].str.contains(search_term, case=False)]
            
        display_cols = ["Title", "Date", "Duration (min)", "Views", "Impressions", "Watch Time (min)", 
                       "Subscriber Gain", "Likes", "Comments", "Shares"]
        
        # Make sure all required columns exist
        for col in display_cols:
            if col not in filtered_data.columns:
                filtered_data[col] = None
                
        st.dataframe(filtered_data[display_cols].sort_values(by="Date", ascending=False), use_container_width=True)
        
        # Calculate and display average metrics for shorts
        shorts_avg_metrics = calculate_avg_metrics(st.session_state.shorts_data)
        
        st.subheader("Average Metrics")
        
        # Display average metrics in multiple columns
        cols = st.columns(3)
        for i, (metric, value) in enumerate(shorts_avg_metrics.items()):
            cols[i % 3].metric(metric, value)
        
        # Visualizations for shorts
        st.subheader("Visualizations")
        
        # Improved bar chart for top shorts by views
        top_n = min(10, len(st.session_state.shorts_data))
        top_shorts = st.session_state.shorts_data.sort_values(by="Views", ascending=False).head(top_n)
        
        # Create shorter titles for visualization
        top_shorts["Short Title"] = top_shorts["Title"].apply(lambda x: x[:25] + "..." if len(x) > 25 else x)
        
        fig1 = px.bar(
            top_shorts,
            x="Short Title",
            y="Views",
            title=f"Top {top_n} Shorts by Views",
            color="Views",
            color_continuous_scale="Reds",
            text="Views"
        )
        fig1.update_layout(
            xaxis_tickangle=-45,
            height=500,
            xaxis_title="",
            yaxis_title="Views",
            margin=dict(l=20, r=20, t=40, b=100)
        )
        fig1.update_traces(texttemplate='%{text:,}', textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)
        
        # Comparison between videos and shorts if videos data is available
        if not st.session_state.video_data.empty:
            st.subheader("Videos vs. Shorts Comparison")
            
            comparison_data = pd.DataFrame({
                'Metric': ['Views', 'Impressions', 'Subscriber Gain'],
                'Videos': [
                    avg_metrics.get('Avg Views', 0),
                    avg_metrics.get('Avg Impressions', 0),
                    avg_metrics.get('Avg Subscriber Gain', 0)
                ],
                'Shorts': [
                    shorts_avg_metrics.get('Avg Views', 0),
                    shorts_avg_metrics.get('Avg Impressions', 0),
                    shorts_avg_metrics.get('Avg Subscriber Gain', 0)
                ]
            })
            
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=comparison_data['Metric'],
                y=comparison_data['Videos'],
                name='Videos',
                marker_color='royalblue'
            ))
            fig3.add_trace(go.Bar(
                x=comparison_data['Metric'],
                y=comparison_data['Shorts'],
                name='Shorts',
                marker_color='tomato'
            ))
            
            fig3.update_layout(
                title='Videos vs. Shorts Comparison',
                xaxis_title='Metric',
                yaxis_title='Value',
                barmode='group'
            )
            
            st.plotly_chart(fig3, use_container_width=True)
        
        # Add table for top 10 shorts by views
        st.subheader("Top 10 Shorts by Views")
        
        # Get top shorts by views
        top_by_views = st.session_state.shorts_data.sort_values(
            by="Views", 
            ascending=False
        ).head(10)
        
        # Display table with the most important metrics
        display_top_cols = ["Title", "Views", "Impressions", "Watch Time (min)", 
                           "Likes", "Comments", "Shares"]
        
        st.dataframe(
            top_by_views[display_top_cols].reset_index(drop=True),
            use_container_width=True
        )
        
        # Display metrics footer
        display_metrics_footer()
    else:
        st.info("No shorts data available.")

# Add refresh button in the sidebar to manually refresh data if needed
with st.sidebar:
    st.subheader("Manual Data Refresh")
    if st.button("Refresh Data"):
        if api_key and channel_id:
            with st.spinner("Refreshing data from YouTube API..."):
                videos_df, shorts_df = fetch_youtube_data(api_key, channel_id)
                
                if videos_df is not None and shorts_df is not None:
                    st.session_state.video_data = videos_df
                    st.session_state.shorts_data = shorts_df
                    st.success("Data refreshed successfully!")
                else:
                    st.error("Failed to refresh data. Using existing data.")
        else:
            st.warning("API credentials required for data refresh.")