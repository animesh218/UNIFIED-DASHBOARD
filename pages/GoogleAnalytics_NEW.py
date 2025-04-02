import streamlit as st
import pandas as pd
import plotly.graph_objs as go
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric

class GA4LandingPageAnalytics:
    def __init__(self, property_id, credentials):
        """
        Initialize GA4 Analytics client with detailed logging
        """
        self.property_id = property_id
        self.client = BetaAnalyticsDataClient(credentials=credentials)
        self.debug_info = []
    
    def fetch_channel_metrics(self, start_date, end_date):
        """
        Fetch metrics for different channels with comprehensive breakdown
        """
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="sessionDefaultChannelGrouping"),
                Dimension(name="deviceCategory"),
                Dimension(name="country")
            ],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="newUsers"),
                Metric(name="sessions"),
                Metric(name="engagedSessions"),
                Metric(name="bounceRate")
            ]
        )
        
        response = self.client.run_report(request)
        
        metrics = {
            "Direct": {"active_users": 0, "new_users": 0, "sessions": 0, 
                       "engaged_sessions": 0, "bounce_rate": 0},
            "Organic Search": {"active_users": 0, "new_users": 0, "sessions": 0, 
                               "engaged_sessions": 0, "bounce_rate": 0},
            "Organic Social": {"active_users": 0, "new_users": 0, "sessions": 0, 
                               "engaged_sessions": 0, "bounce_rate": 0}
        }
        
        # Reset debug information
        self.debug_info = []
        
        for row in response.rows:
            channel = row.dimension_values[0].value
            device = row.dimension_values[1].value
            country = row.dimension_values[2].value
            
            if channel in metrics:
                # Extract metric values
                active_users = int(row.metric_values[0].value)
                new_users = int(row.metric_values[1].value)
                sessions = int(row.metric_values[2].value)
                engaged_sessions = int(row.metric_values[3].value)
                bounce_rate = float(row.metric_values[4].value)
                
                # Accumulate metrics
                metrics[channel]["active_users"] += active_users
                metrics[channel]["new_users"] += new_users
                metrics[channel]["sessions"] += sessions
                metrics[channel]["engaged_sessions"] += engaged_sessions
                metrics[channel]["bounce_rate"] += bounce_rate
                
                # Store debug information
                self.debug_info.append({
                    "Channel": channel,
                    "Device": device,
                    "Country": country,
                    "Active Users": active_users,
                    "New Users": new_users,
                    "Total Sessions": sessions,
                    "Engaged Sessions": engaged_sessions,
                    "Bounce Rate (%)": bounce_rate
                })
        
        return metrics
    
    def fetch_landing_page_metrics(self, start_date, end_date):
        """
        Fetch metrics for landing pages
        """
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="landingPage")
            ],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="newUsers"),
                Metric(name="sessions"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration")
            ]
        )
        
        response = self.client.run_report(request)
        
        landing_pages = []
        for row in response.rows:
            landing_page = row.dimension_values[0].value
            landing_pages.append({
                "Landing Page": landing_page,
                "Active Users": int(row.metric_values[0].value),
                "New Users": int(row.metric_values[1].value),
                "Sessions": int(row.metric_values[2].value),
                "Bounce Rate (%)": round(float(row.metric_values[3].value), 2),
                "Avg Session Duration (sec)": round(float(row.metric_values[4].value), 2)
            })
        
        # Sort by sessions in descending order
        landing_pages_df = pd.DataFrame(landing_pages)
        return landing_pages_df.sort_values("Sessions", ascending=False).head(10)

def calculate_percentage_change(previous, current):
    """
    Calculate percentage change between two values
    """
    if previous == 0:
        return "N/A" if current == 0 else "New"
    
    change = ((current - previous) / previous) * 100
    return f"{change:.2f}%"

def main():
    st.set_page_config(page_title="GA4 Metrics Dashboard", layout="wide")
    st.title("📊 GA4 Comprehensive Metrics Dashboard")
    
    # Sidebar for configuration
    st.sidebar.header("Dashboard Configuration")
    
    # JSON key file upload
    json_file = st.sidebar.file_uploader("Upload Google Service Account JSON", type=["json"])
    
    if json_file:
        try:
            # Parse JSON credentials
            json_key = json_file.read()
            json_key = eval(json_key.decode("utf-8"))
            credentials = service_account.Credentials.from_service_account_info(json_key)
            
            # Property ID input
            property_id = st.sidebar.text_input("Enter GA4 Property ID", key="property_id")
            
            if property_id:
                # Date range selection
                st.sidebar.subheader("Select Date Ranges for Comparison")
                
                # First date range
                st.sidebar.markdown("**First Date Range**")
                start_date_1 = st.sidebar.date_input("Start Date (First Period)", 
                                                     pd.Timestamp.today() - pd.Timedelta(days=14),
                                                     key="start_date_1")
                end_date_1 = st.sidebar.date_input("End Date (First Period)", 
                                                   pd.Timestamp.today() - pd.Timedelta(days=7),
                                                   key="end_date_1")
                
                # Second date range
                st.sidebar.markdown("**Second Date Range**")
                start_date_2 = st.sidebar.date_input("Start Date (Second Period)", 
                                                     pd.Timestamp.today() - pd.Timedelta(days=7),
                                                     key="start_date_2")
                end_date_2 = st.sidebar.date_input("End Date (Second Period)", 
                                                   pd.Timestamp.today(),
                                                   key="end_date_2")
                
                # Initialize GA4 Analytics
                ga4_analytics = GA4LandingPageAnalytics(property_id, credentials)
                
                # Create tabs
                tab1, tab2, tab3 = st.tabs(["Channel Metrics", "Landing Page Analysis", "Debug Information"])
                
                # Fetch data button
                if st.sidebar.button("Compare Metrics"):
                    with st.spinner("Fetching and comparing metrics..."):
                        # Fetch channel metrics for both periods
                        metrics_1 = ga4_analytics.fetch_channel_metrics(
                            start_date_1.strftime("%Y-%m-%d"), 
                            end_date_1.strftime("%Y-%m-%d")
                        )
                        metrics_2 = ga4_analytics.fetch_channel_metrics(
                            start_date_2.strftime("%Y-%m-%d"), 
                            end_date_2.strftime("%Y-%m-%d")
                        )
                        
                        # Fetch landing page metrics for both periods
                        landing_pages_1 = ga4_analytics.fetch_landing_page_metrics(
                            start_date_1.strftime("%Y-%m-%d"), 
                            end_date_1.strftime("%Y-%m-%d")
                        )
                        landing_pages_2 = ga4_analytics.fetch_landing_page_metrics(
                            start_date_2.strftime("%Y-%m-%d"), 
                            end_date_2.strftime("%Y-%m-%d")
                        )
                    
                    # Tab 1: Channel Metrics
                    with tab1:
                        # Prepare comparison data for channels
                        comparison_data = []
                        metrics_to_compare = ["active_users", "new_users", "sessions"]
                        
                        for channel in ["Direct", "Organic Search", "Organic Social"]:
                            channel_data = {
                                "Channel": channel,
                            }
                            
                            for metric in metrics_to_compare:
                                prev_value = metrics_1[channel][metric]
                                curr_value = metrics_2[channel][metric]
                                
                                channel_data[f"{metric.replace('_', ' ').title()} (Period 1)"] = prev_value
                                channel_data[f"{metric.replace('_', ' ').title()} (Period 2)"] = curr_value
                                channel_data[f"{metric.replace('_', ' ').title()} Change"] = calculate_percentage_change(prev_value, curr_value)
                            
                            comparison_data.append(channel_data)
                        
                        # Create DataFrame and display
                        comparison_df = pd.DataFrame(comparison_data)
                        st.dataframe(comparison_df, use_container_width=True)
                        
                        # Visualizations for Channel Metrics
                        st.subheader("Channel Metrics Visualizations")
                        metrics_to_plot = ["Active Users", "New Users", "Sessions"]
                        
                        for metric in metrics_to_plot:
                            # Prepare data for plotting
                            period_1_data = [metrics_1[channel][metric.lower().replace(' ', '_')] for channel in ["Direct", "Organic Search", "Organic Social"]]
                            period_2_data = [metrics_2[channel][metric.lower().replace(' ', '_')] for channel in ["Direct", "Organic Search", "Organic Social"]]
                            
                            # Create comparison bar chart
                            fig = go.Figure(data=[
                                go.Bar(name="Period 1", x=["Direct", "Organic Search", "Organic Social"], y=period_1_data),
                                go.Bar(name="Period 2", x=["Direct", "Organic Search", "Organic Social"], y=period_2_data)
                            ])
                            fig.update_layout(
                                title=f"{metric} Comparison",
                                xaxis_title="Channel",
                                yaxis_title=metric
                            )
                            st.plotly_chart(fig)
                    
                    # Tab 2: Landing Page Analysis
                    with tab2:
                        st.subheader("Top 10 Landing Pages - First Period")
                        st.dataframe(landing_pages_1, use_container_width=True)
                        
                        st.subheader("Top 10 Landing Pages - Second Period")
                        st.dataframe(landing_pages_2, use_container_width=True)
                        
                        # Comparison of landing pages
                        st.subheader("Landing Page Metrics Comparison")
                        
                        # Merge landing pages from both periods
                        merged_pages = pd.merge(
                            landing_pages_1, 
                            landing_pages_2, 
                            on="Landing Page", 
                            suffixes=('_Period1', '_Period2')
                        )
                        
                        # Calculate changes
                        metrics_to_compare = [
                            "Active Users", 
                            "New Users", 
                            "Sessions", 
                            "Bounce Rate (%)", 
                            "Avg Session Duration (sec)"
                        ]
                        
                        for metric in metrics_to_compare:
                            merged_pages[f"{metric} Change"] = merged_pages.apply(
                                lambda row: calculate_percentage_change(
                                    row[f"{metric}_Period1"], 
                                    row[f"{metric}_Period2"]
                                ), 
                                axis=1
                            )
                        
                        # Display comparison
                        st.dataframe(merged_pages, use_container_width=True)
                        
                        # Visualizations for Landing Pages
                        st.subheader("Landing Page Metrics Visualizations")
                        metrics_to_plot = ["Active Users", "Sessions"]
                        
                        for metric in metrics_to_plot:
                            # Top 5 landing pages
                            top_pages_1 = landing_pages_1.nlargest(5, "Sessions")
                            top_pages_2 = landing_pages_2.nlargest(5, "Sessions")
                            
                            # Create comparison bar chart
                            fig = go.Figure(data=[
                                go.Bar(name="Period 1", x=top_pages_1["Landing Page"], y=top_pages_1[metric]),
                                go.Bar(name="Period 2", x=top_pages_2["Landing Page"], y=top_pages_2[metric])
                            ])
                            fig.update_layout(
                                title=f"Top 5 Landing Pages - {metric} Comparison",
                                xaxis_title="Landing Page",
                                yaxis_title=metric,
                                xaxis_tickangle=-45
                            )
                            st.plotly_chart(fig)
                    
                    # Tab 3: Debug Information
                    with tab3:
                        st.subheader("Detailed Debug Information")
                        debug_df = pd.DataFrame(ga4_analytics.debug_info)
                        st.dataframe(debug_df, use_container_width=True)
        
        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()