import streamlit as st
import tweepy
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from functools import lru_cache

# Load environment variables once at startup
load_dotenv()

# Twitter API credentials
bearer_token = os.getenv("BEARER_TOKEN")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
user_id = os.getenv("USER_ID")

# Set page configuration
st.set_page_config(
    page_title="Twitter Analytics Dashboard",
    page_icon="🐦",
    layout="wide"
)

# Add CSS styling - moved to a separate function to improve readability
def load_css():
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #1DA1F2;
            text-align: center;
            margin-bottom: 1rem;
        }
        .metric-card {
            background-color: #f0f2f5;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #1DA1F2;
        }
        .metric-label {
            font-size: 1rem;
            color: #657786;
        }
        .debug-info {
            background-color: #f8f9fa;
            border-left: 3px solid #1DA1F2;
            padding: 10px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)

# Load CSS
load_css()

# Header
st.markdown("<h1 class='main-header'>Twitter Analytics Dashboard</h1>", unsafe_allow_html=True)

# Initialize Twitter API client - using lazy initialization

def get_twitter_clients():
    """Initialize and cache Twitter API clients"""
    # Initialize the v2 client
    client_v2 = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        wait_on_rate_limit=True
    )

    # Initialize v1 API for backward compatibility
    auth = tweepy.OAuth1UserHandler(api_key, api_secret)
    api_v1 = tweepy.API(auth)
    
    return client_v2, api_v1

# Get user ID from username - separate function with caching
@lru_cache(maxsize=100)
def get_user_id(username, client_v2):
    """Get user ID from username with caching for better performance"""
    user = client_v2.get_user(username=username)
    if not user or not user.data:
        return None
    return user.data.id

# Function to fetch tweets with pagination - optimized for efficiency
@st.cache_data(ttl=600)  # Cache data for 10 minutes to reduce API calls
def fetch_tweets(username=None, user_id=None, start_date=None, end_date=None, max_results=100, debug_mode=False):
    """Optimized function to fetch tweets with date range"""
    client_v2, api_v1 = get_twitter_clients()
    
    try:
        # Get user ID if username is provided
        if username:
            user_id = get_user_id(username, client_v2)
            if not user_id:
                st.error(f"User {username} not found")
                return None, {"error": "User not found"}
            
            if debug_mode:
                st.info(f"Resolved username {username} to user_id {user_id}")
        
        # Set up time parameters
        end_time = end_date if end_date else datetime.utcnow()
        start_time = start_date if start_date else None
        
        # Format dates for the Twitter API
        end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ') if start_time else None
        
        # Debug information
        debug_info = {
            "user_id": user_id,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "max_results_requested": max_results,
        }
        
        # Optimize API calls by using larger page sizes
        page_size = min(100, max_results)  # Twitter API limit is 100
        all_tweets = []
        
        # Prefetch tweet fields to minimize API calls
        tweet_fields = ['created_at', 'public_metrics', 'entities']
        expansions = ['attachments.media_keys']
        
        # Use pagination token for efficient retrieval
        pagination_token = None
        tweets_fetched = 0
        
        # Fetch tweets with optimized pagination
        while tweets_fetched < max_results:
            try:
                # Calculate remaining tweets to fetch
                current_request_size = min(page_size, max_results - tweets_fetched)
                
                # Build API request parameters
                params = {
                    'id': user_id,
                    'max_results': current_request_size,
                    'end_time': end_time_str,
                    'tweet_fields': tweet_fields,
                    'expansions': expansions,
                    'pagination_token': pagination_token
                }
                
                # Add start_time if provided
                if start_time_str:
                    params['start_time'] = start_time_str
                
                # Make API request
                response = client_v2.get_users_tweets(**params)
                
                # Check if we got any data
                if not response or not response.data:
                    # Try fallback method if first attempt failed
                    if not all_tweets:
                        return use_fallback_method(username, user_id, start_date, end_date, max_results, debug_mode)
                    break
                
                # Process tweets - more efficient data extraction
                for tweet in response.data:
                    metrics = tweet.public_metrics
                    
                    tweet_data = {
                        'id': tweet.id,
                        'text': tweet.text,
                        'created_at': tweet.created_at,
                        'likes': metrics['like_count'],
                        'retweets': metrics['retweet_count'],
                        'replies': metrics['reply_count'],
                        'quotes': metrics['quote_count'],
                        'impressions': metrics.get('impression_count', 0),
                        'has_media': hasattr(tweet, 'attachments')
                    }
                    all_tweets.append(tweet_data)
                
                # Update counter
                tweets_fetched += len(response.data)
                
                # Check if we have a next token for pagination
                if hasattr(response, 'meta') and 'next_token' in response.meta:
                    pagination_token = response.meta['next_token']
                else:
                    break  # No more pages
                    
            except tweepy.TweepyException as e:
                if debug_mode:
                    st.error(f"API error: {e}")
                
                # Try fallback if main method failed
                if not all_tweets:
                    return use_fallback_method(username, user_id, start_date, end_date, max_results, debug_mode)
                break
        
        # Create dataframe
        if all_tweets:
            df_tweets = pd.DataFrame(all_tweets)
            debug_info["tweets_returned"] = len(df_tweets)
            return df_tweets, debug_info
        else:
            return use_fallback_method(username, user_id, start_date, end_date, max_results, debug_mode)
    
    except Exception as e:
        if debug_mode:
            st.error(f"Error in fetch_tweets: {e}")
        return None, {"error": str(e)}

# Fallback method - simplified for better performance
def use_fallback_method(username=None, user_id=None, start_date=None, end_date=None, max_results=100, debug_mode=False):
    """Optimized fallback method to fetch tweets"""
    _, api_v1 = get_twitter_clients()
    
    try:
        fallback_tweets = []
        debug_info = {"method": "fallback_v1"}
        
        # Use cursor more efficiently
        cursor = tweepy.Cursor(
            api_v1.user_timeline,
            screen_name=username if username else None,
            user_id=user_id if not username else None,
            count=200,  # Max allowed per request to reduce API calls
            tweet_mode='extended',
            exclude_replies=False,
            include_rts=True
        ).items(max_results)
        
        # Process tweets in batches to improve performance
        for tweet in cursor:
            tweet_data = {
                'id': tweet.id,
                'text': tweet.full_text,
                'created_at': tweet.created_at,
                'likes': tweet.favorite_count,
                'retweets': tweet.retweet_count,
                'replies': 0,
                'quotes': 0,
                'impressions': 0,
                'has_media': hasattr(tweet, 'entities') and 'media' in tweet.entities
            }
            
            # Filter by date range if specified
            if start_date and tweet.created_at < start_date:
                continue
            if end_date and tweet.created_at > end_date:
                continue
                
            fallback_tweets.append(tweet_data)
        
        if fallback_tweets:
            df_tweets = pd.DataFrame(fallback_tweets)
            debug_info["tweets_returned"] = len(fallback_tweets)
            return df_tweets, debug_info
        else:
            return None, {"error": "No tweets found with either method"}
            
    except Exception as e:
        if debug_mode:
            st.error(f"Fallback method error: {e}")
        return None, {"error_fallback": str(e)}

# Function to efficiently enrich tweet data with engagement metrics
def enrich_tweet_data(df):
    """Add derived metrics to the tweet dataframe - optimized version"""
    if df is None or df.empty:
        return None
    
    # Use vectorized operations instead of apply for better performance
    df['total_engagement'] = df['likes'] + df['retweets'] + df['replies'] + df['quotes']
    
    # Vectorized operations for engagement rate
    df['engagement_rate'] = 0  # Default value
    mask = df['impressions'] > 0
    df.loc[mask, 'engagement_rate'] = (df.loc[mask, 'total_engagement'] / df.loc[mask, 'impressions']) * 100
    
    # Vectorized weighted engagement score
    df['engagement_score'] = (
        df['likes'] * 1 + 
        df['retweets'] * 2 + 
        df['replies'] * 1.5 + 
        df['quotes'] * 1.5
    )
    
    # Vectorized time-based metrics
    df['hour_of_day'] = df['created_at'].dt.hour
    df['day_of_week'] = df['created_at'].dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5)
    
    # Vectorized text length
    df['text_length'] = df['text'].str.len()
    
    # Precompute date column for aggregations
    df['date'] = df['created_at'].dt.date
    
    return df

# Sidebar for user input
st.sidebar.header("Settings")

# Input method selection
input_method = st.sidebar.radio("Select input method:", ["Username", "User ID"])

if input_method == "Username":
    username = st.sidebar.text_input("Enter Twitter username (without @):")
    user_identifier = username if username else None
    use_user_id = False
else:
    custom_user_id = st.sidebar.text_input("Enter User ID:", user_id)
    user_identifier = custom_user_id if custom_user_id else user_id
    use_user_id = True

# Analysis parameters
st.sidebar.subheader("Analysis Parameters")

# Date range options
date_option = st.sidebar.radio("Select date range:", ["All available data", "Custom date range"])

start_date = None
end_date = None

if date_option == "Custom date range":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start date:", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End date:", datetime.now())
    
    # Convert to datetime objects with time set to beginning/end of day
    start_date = datetime.combine(start_date, datetime.min.time())
    end_date = datetime.combine(end_date, datetime.max.time())

max_results = st.sidebar.slider("Maximum tweets to analyze:", 10, 1000, 200)

# Debug mode
debug_mode = st.sidebar.checkbox("Debug mode")

# Add a button to refresh data
refresh_btn = st.sidebar.button("Refresh Data")

# Main dashboard content
st.subheader("Tweet Analytics")

# Main analysis logic
if user_identifier:
    # Show loading spinner while fetching data
    with st.spinner("Fetching Twitter data..."):
        # Force refresh if button is clicked
        if refresh_btn:
            st.cache_data.clear()
        
        # Fetch data
        if use_user_id:
            df_tweets, debug_info = fetch_tweets(
                user_id=user_identifier, 
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
                debug_mode=debug_mode
            )
            
        else:
            df_tweets, debug_info = fetch_tweets(
                username=user_identifier, 
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
                debug_mode=debug_mode
            )
        
        # Display debug information if requested
        if debug_mode and debug_info:
            with st.expander("Debug Information"):
                st.json(debug_info)
    
    # Process and display data if available
    if df_tweets is not None and not df_tweets.empty:
        # Enrich tweet data with additional metrics
        df_tweets = enrich_tweet_data(df_tweets)
        
        # Display tweet count and date range
        st.success(f"Successfully retrieved {len(df_tweets)} tweets from {df_tweets['created_at'].min().strftime('%b %d, %Y')} to {df_tweets['created_at'].max().strftime('%b %d, %Y')}")
        
        # Calculate metrics - use vectorized operations
        total_tweets = len(df_tweets)
        avg_likes = df_tweets['likes'].mean()
        avg_retweets = df_tweets['retweets'].mean()
        avg_replies = df_tweets['replies'].mean()
        
        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total_tweets}</div>
                <div class="metric-label">Total Tweets</div>
            </div></div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{avg_likes:.1f}</div>
                <div class="metric-label">Avg Likes</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{avg_retweets:.1f}</div>
                <div class="metric-label">Avg Retweets</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{avg_replies:.1f}</div>
                <div class="metric-label">Avg Replies</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Create tabs for different analyses
        tab1, tab2, tab3, tab4 = st.tabs(["Engagement Analysis", "Time Analysis", "Content Analysis", "Top Tweets"])
        
        with tab1:
            st.subheader("Engagement Metrics")
            
            # Engagement over time
            st.write("### Engagement Over Time")
            daily_engagement = df_tweets.groupby('date').agg({
                'likes': 'sum',
                'retweets': 'sum',
                'replies': 'sum',
                'quotes': 'sum',
                'total_engagement': 'sum'
            }).reset_index()
            
            fig_engagement = px.line(
                daily_engagement, 
                x='date', 
                y=['likes', 'retweets', 'replies', 'quotes'],
                title="Daily Engagement Metrics",
                labels={'value': 'Count', 'variable': 'Metric', 'date': 'Date'},
                line_shape='spline',
                template="plotly_white"
            )
            st.plotly_chart(fig_engagement, use_container_width=True)
            
            # Media engagement comparison
            st.write("### Media vs. No Media Engagement")
            media_comparison = df_tweets.groupby('has_media').agg({
                'likes': 'mean',
                'retweets': 'mean',
                'replies': 'mean',
                'quotes': 'mean',
                'total_engagement': 'mean'
            }).reset_index()
            
            media_comparison['has_media'] = media_comparison['has_media'].map({True: 'With Media', False: 'No Media'})
            
            fig_media = px.bar(
                media_comparison,
                x='has_media',
                y=['likes', 'retweets', 'replies', 'quotes'],
                title="Media vs. No Media Engagement",
                barmode='group',
                labels={'value': 'Average Count', 'variable': 'Metric', 'has_media': 'Media Type'},
                template="plotly_white"
            )
            st.plotly_chart(fig_media, use_container_width=True)
        
        with tab2:
            st.subheader("Time-Based Analysis")
            
            # Best time of day
            st.write("### Engagement by Hour of Day")
            hourly_engagement = df_tweets.groupby('hour_of_day').agg({
                'likes': 'mean',
                'retweets': 'mean',
                'total_engagement': 'mean',
                'id': 'count'
            }).reset_index()
            
            hourly_engagement.rename(columns={'id': 'tweet_count'}, inplace=True)
            
            fig_hourly = px.line(
                hourly_engagement,
                x='hour_of_day',
                y='total_engagement',
                title="Average Engagement by Hour of Day",
                labels={'total_engagement': 'Avg Engagement', 'hour_of_day': 'Hour (UTC)'},
                template="plotly_white"
            )
            
            fig_hourly.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=2))
            st.plotly_chart(fig_hourly, use_container_width=True)
            
            # Day of week analysis
            st.write("### Engagement by Day of Week")
            dow_mapping = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 
                          4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
            
            df_tweets['day_name'] = df_tweets['day_of_week'].map(dow_mapping)
            
            dow_engagement = df_tweets.groupby('day_name').agg({
                'likes': 'mean',
                'retweets': 'mean',
                'total_engagement': 'mean',
                'id': 'count'
            }).reset_index()
            
            dow_engagement.rename(columns={'id': 'tweet_count'}, inplace=True)
            
            # Custom sort for days of week
            dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            dow_engagement['day_name'] = pd.Categorical(dow_engagement['day_name'], categories=dow_order, ordered=True)
            dow_engagement = dow_engagement.sort_values('day_name')
            
            fig_dow = px.bar(
                dow_engagement,
                x='day_name',
                y=['likes', 'retweets', 'total_engagement'],
                title="Average Engagement by Day of Week",
                barmode='group',
                labels={'value': 'Average', 'variable': 'Metric', 'day_name': 'Day'},
                template="plotly_white"
            )
            st.plotly_chart(fig_dow, use_container_width=True)

        with tab3:
            st.subheader("Content Analysis")
            
            # Text length vs engagement
            st.write("### Text Length vs. Engagement")
            # Group by text length ranges for better visualization
            df_tweets['text_length_bin'] = pd.cut(
                df_tweets['text_length'], 
                bins=[0, 50, 100, 150, 200, 250, 280],
                labels=['0-50', '51-100', '101-150', '151-200', '201-250', '251-280']
            )
            
            length_engagement = df_tweets.groupby('text_length_bin').agg({
                'likes': 'mean',
                'retweets': 'mean',
                'total_engagement': 'mean',
                'id': 'count'
            }).reset_index()
            
            length_engagement.rename(columns={'id': 'tweet_count'}, inplace=True)
            
            fig_length = px.bar(
                length_engagement,
                x='text_length_bin',
                y='total_engagement',
                title="Average Engagement by Tweet Length",
                labels={'total_engagement': 'Avg Engagement', 'text_length_bin': 'Character Count Range'},
                template="plotly_white"
            )
            st.plotly_chart(fig_length, use_container_width=True)
            
            # Tweet frequency over time
            st.write("### Tweet Frequency Over Time")
            tweet_frequency = df_tweets.groupby('date').size().reset_index(name='count')
            
            fig_frequency = px.line(
                tweet_frequency,
                x='date',
                y='count',
                title="Daily Tweet Frequency",
                labels={'count': 'Number of Tweets', 'date': 'Date'},
                template="plotly_white"
            )
            st.plotly_chart(fig_frequency, use_container_width=True)
        
        with tab4:
            st.subheader("Top Performing Tweets")
            
            # Sort options
            sort_by = st.selectbox(
                "Sort tweets by:",
                ["Likes", "Retweets", "Replies", "Total Engagement", "Engagement Score"]
            )
            
            # Map selection to column name
            sort_map = {
                "Likes": "likes",
                "Retweets": "retweets",
                "Replies": "replies",
                "Total Engagement": "total_engagement",
                "Engagement Score": "engagement_score"
            }
            
            # Get top tweets
            top_tweets = df_tweets.sort_values(by=sort_map[sort_by], ascending=False).head(10)
            
            # Display top tweets
            for i, tweet in enumerate(top_tweets.itertuples(), 1):
                st.markdown(f"""
                <div style="border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin-bottom: 15px;">
                    <h4>#{i} - Tweet from {tweet.created_at.strftime('%b %d, %Y')}</h4>
                    <p>{tweet.text}</p>
                    <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                        <span>❤️ {tweet.likes}</span>
                        <span>🔄 {tweet.retweets}</span>
                        <span>💬 {tweet.replies}</span>
                        <span>📊 Total: {tweet.total_engagement}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Data explorer section for raw data analysis
        with st.expander("Data Explorer"):
            st.dataframe(df_tweets[['created_at', 'text', 'likes', 'retweets', 'replies', 'quotes', 'total_engagement', 'engagement_score']])
            
            # Export options
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download as CSV",
                    data=df_tweets.to_csv(index=False).encode('utf-8'),
                    file_name=f"twitter_analytics_{user_identifier}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            with col2:
                st.download_button(
                    label="Download as Excel",
                    data=df_tweets.to_excel(index=False).encode('utf-8'),
                    file_name=f"twitter_analytics_{user_identifier}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
    
    elif debug_info and "error" in debug_info:
        st.error(f"Error retrieving data: {debug_info['error']}")
    else:
        st.warning("No tweets found. Try adjusting your filters or check the username/user ID.")

else:
    st.info("Enter a Twitter username or user ID in the sidebar to get started.")

# Footer
st.markdown("---")
st.markdown("## About This Dashboard")
st.markdown("""
This Twitter Analytics Dashboard helps you analyze Twitter engagement metrics, posting patterns, and content performance.
To get started, enter your Twitter username or user ID in the sidebar.

**Features:**
- Engagement analysis (likes, retweets, replies)
- Time-based analysis (best posting times)
- Content analysis (optimal tweet length)
- Top performing tweets

**Note:** This dashboard uses the Twitter API v2. For private metrics like impressions, you need to authenticate with your own account.
""")

# Add a footer with version info
st.markdown("---")
st.markdown(f"<p style='text-align: center; color: gray;'>Twitter Analytics Dashboard v1.0.0 | Last updated: {datetime.now().strftime('%b %d, %Y')}</p>", unsafe_allow_html=True)
