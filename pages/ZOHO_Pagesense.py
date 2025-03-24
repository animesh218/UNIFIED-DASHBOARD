import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import base64
import io
from io import BytesIO
import re

# Set styling for better visualizations
plt.style.use('ggplot')
sns.set_palette("pastel")
# Remove grid lines from the plots
plt.rcParams['axes.grid'] = False

def convert_duration(duration):
    """Convert duration string to total seconds."""
    if pd.isna(duration) or duration == "":
        return 0
    
    match = re.match(r'(?:(\d+)m )?(\d+)s', str(duration))
    if match:
        minutes = int(match.group(1)) if match.group(1) else 0
        seconds = int(match.group(2))
        return minutes * 60 + seconds
    return 0

def shorten_labels(labels, max_length=15):
    """Shorten long labels for better visualization."""
    return [label[:max_length] + '...' if len(label) > max_length else label for label in labels]

def get_table_download_link(df, filename="analytics_report.csv", text="Download Report as CSV"):
    """Generates a link to download the dataframe as a CSV file"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

def export_plots_to_pdf(figures, filename="analytics_report.pdf"):
    """Export all plots to a single PDF file"""
    from matplotlib.backends.backend_pdf import PdfPages
    
    buffer = BytesIO()
    with PdfPages(buffer) as pdf:
        for fig in figures:
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    
    buffer.seek(0)
    return buffer

def get_pdf_download_link(buffer, filename="analytics_report.pdf", text="Download Report as PDF"):
    """Generates a link to download the PDF file"""
    b64 = base64.b64encode(buffer.read()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Format dataframe for display
def format_dataframe(df):
    """Format numeric columns to have max 2 decimal places"""
    formatted_df = df.copy()
    
    # Format numeric columns to max 2 decimal places
    for col in df.select_dtypes(include=['float', 'int']).columns:
        formatted_df[col] = formatted_df[col].round(2)
    
    return formatted_df

# Streamlit UI
st.set_page_config(layout="wide", page_title="Website Analytics Dashboard")

st.title("Website Analytics Dashboard")
st.markdown("---")

# Allow user to select between single file or multiple files
upload_mode = st.radio("Upload Mode", ["Single File", "Multiple Files"])

if upload_mode == "Single File":
    uploaded_file = st.file_uploader("Upload Landing Page Analytics CSV", type=["csv"])
    
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file, skiprows=1)
        df.columns = df.columns.str.strip()
        
        # Extract relevant columns
        df = df[["Landing Page", "% New Sessions", "New Visitors", "Average Session Duration"]]
        df["% New Sessions"] = df["% New Sessions"].str.replace('%', '', regex=True).astype(float)
        df["New Visitors"] = pd.to_numeric(df["New Visitors"], errors='coerce').fillna(0).astype(int)
        df["Average Session Duration"] = df["Average Session Duration"].apply(convert_duration)
        
        # Create short labels for visualization but don't show in table
        short_labels = shorten_labels(df["Landing Page"], max_length=15)
        
        st.markdown("### Processed Data")
        # Apply formatting but remove background gradient (CHANGE #2)
        formatted_df = format_dataframe(df)
        st.dataframe(formatted_df)
        
        # Download option
        st.markdown(get_table_download_link(df), unsafe_allow_html=True)
        
        # Collect all figures for PDF export
        all_figures = []
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### % New Sessions by Landing Page")
            fig1, ax1 = plt.subplots(figsize=(10, 6))
            bars = sns.barplot(x=short_labels, y=df["% New Sessions"], ax=ax1, palette="Blues_d", edgecolor=None)
            ax1.set_xlabel("Landing Page")
            ax1.set_ylabel("% New Sessions")
            ax1.set_title("% New Sessions by Landing Page")
            plt.xticks(rotation=45, ha='right')
            
            # Add value labels on top of bars
            for bar in bars.patches:
                bars.annotate(f'{bar.get_height():.2f}%',
                             (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                             ha='center', va='bottom', fontsize=8)
            
            st.pyplot(fig1)
            all_figures.append(fig1)
        
        with col2:
            st.markdown("### New Visitors by Landing Page")
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            bars = sns.barplot(x=short_labels, y=df["New Visitors"], ax=ax2, palette="Blues_d", edgecolor=None)
            ax2.set_xlabel("Landing Page")
            ax2.set_ylabel("New Visitors")
            ax2.set_title("New Visitors by Landing Page")
            plt.xticks(rotation=45, ha='right')
            
            # Add value labels on top of bars
            for bar in bars.patches:
                bars.annotate(f'{int(bar.get_height())}',
                             (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                             ha='center', va='bottom', fontsize=8)
            
            st.pyplot(fig2)
            all_figures.append(fig2)
        
        st.markdown("### Average Session Duration by Landing Page")
        fig3, ax3 = plt.subplots(figsize=(12, 6))
        bars = sns.barplot(x=short_labels, y=df["Average Session Duration"], ax=ax3, palette="Blues_d", edgecolor=None)
        ax3.set_xlabel("Landing Page")
        ax3.set_ylabel("Session Duration (s)")
        ax3.set_title("Average Session Duration by Landing Page")
        plt.xticks(rotation=45, ha='right')
        
        # Add value labels on top of bars
        for bar in bars.patches:
            bars.annotate(f'{int(bar.get_height())}s',
                         (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                         ha='center', va='bottom', fontsize=8)
        
        st.pyplot(fig3)
        all_figures.append(fig3)
        
        # PDF Export
        pdf_buffer = export_plots_to_pdf(all_figures)
        st.markdown("### Download Complete Report")
        st.markdown(get_pdf_download_link(pdf_buffer), unsafe_allow_html=True)

else:  # Multiple Files
    uploaded_files = st.file_uploader("Upload CSV Files", type=["csv"], accept_multiple_files=True)
    
    data_frames = []
    file_types = []
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            df = pd.read_csv(uploaded_file, skiprows=1)
            df.columns = df.columns.str.strip()
            
            # Determine file type and process accordingly
            if "Landing Page" in df.columns:
                # Landing page analytics file
                processed_df = df[["Landing Page", "% New Sessions", "New Visitors", "Average Session Duration"]]
                processed_df["% New Sessions"] = processed_df["% New Sessions"].str.replace('%', '', regex=True).astype(float)
                processed_df["New Visitors"] = pd.to_numeric(processed_df["New Visitors"], errors='coerce').fillna(0).astype(int)
                processed_df["Average Session Duration"] = processed_df["Average Session Duration"].apply(convert_duration)
                processed_df.rename(columns={"Landing Page": "Page"}, inplace=True)
                file_types.append(("landing_page", file_name))
            elif "Page" in df.columns:
                # Page analytics file
                processed_df = df[["Page", "Page Views", "Average Time on page"]]
                processed_df["Page Views"] = pd.to_numeric(processed_df["Page Views"], errors='coerce').fillna(0).astype(int)
                processed_df["Average Time on page"] = processed_df["Average Time on page"].apply(convert_duration)
                file_types.append(("page_analytics", file_name))
            else:
                st.error(f"Unknown file format: {file_name}")
                continue
            
            # Store original source file for filtering but don't show in displayed table
            processed_df["_source_file"] = file_name
            data_frames.append(processed_df)
        
        if data_frames:
            # Merge data
            final_df = pd.concat(data_frames, ignore_index=True)
            
            # CHANGE #1: Merge data for pages with the same name
            # Group by Page name and aggregate metrics
            # Define aggregation function for each column type
            agg_functions = {col: 'mean' for col in final_df.columns if col != 'Page' and col != '_source_file'}
            # Keep track of source files for each page
            final_df['_source_files'] = final_df['_source_file']
            agg_functions['_source_files'] = lambda x: ', '.join(set(x))
            # Group and aggregate
            merged_df = final_df.groupby('Page').agg(agg_functions).reset_index()
            
            st.markdown("### Processed Data")
            # Display all columns except the hidden source file columns
            display_cols = [col for col in merged_df.columns if not col.startswith('_source_')]
            
            # CHANGE #3: Format to 2 decimal places (this is enhanced in the format_dataframe function)
            formatted_df = format_dataframe(merged_df[display_cols])
            
            # CHANGE #2: Remove background gradient (now transparent)
            st.dataframe(formatted_df)
            
            # Download option
            st.markdown(get_table_download_link(merged_df[display_cols]), unsafe_allow_html=True)
            
            # Add filter by source file
            if len(data_frames) > 1:
                all_source_files = [ft[1] for ft in file_types]
                selected_file = st.selectbox("Filter by file:", ["All Files"] + all_source_files)
                if selected_file != "All Files":
                    # Filter to include pages from the selected file
                    filtered_pages = final_df[final_df["_source_file"] == selected_file]["Page"].unique()
                    display_df = merged_df[merged_df["Page"].isin(filtered_pages)].copy()
                else:
                    display_df = merged_df.copy()
            else:
                display_df = merged_df.copy()
            
            # Create short labels for visualization
            display_df["_short_page"] = shorten_labels(display_df["Page"], max_length=15)
            
            # Collect all figures for PDF export
            all_figures = []
            
            # Function to plot improved graphs
            def plot_improved_graph(df, y_col, title, color_palette):
                if not df.empty and y_col in df.columns and df[y_col].notna().any():
                    fig, ax = plt.subplots(figsize=(12, 6))
                    bars = sns.barplot(x=df["_short_page"], y=df[y_col], ax=ax, palette=color_palette, edgecolor=None)
                    ax.set_xlabel("Page")
                    ax.set_ylabel(y_col)
                    ax.set_title(title)
                    plt.xticks(rotation=45, ha='right')
                    
                    # Add value labels on top of bars
                    for bar in bars.patches:
                        if y_col == "% New Sessions":
                            value = f"{bar.get_height():.2f}%"
                        elif "Duration" in y_col or "Time" in y_col:
                            value = f"{int(bar.get_height())}s"
                        else:
                            value = f"{int(bar.get_height())}"
                            
                        bars.annotate(value,
                                     (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                                     ha='center', va='bottom', fontsize=8)
                    
                    st.pyplot(fig)
                    all_figures.append(fig)
                    return fig
                return None
            
            # Visualizations
            st.markdown("### Visualizations")
            
            # Use column layout for better space utilization
            metrics = []
            if "% New Sessions" in display_df.columns:
                metrics.append(("% New Sessions", "New Sessions %", "Blues_d"))
            if "New Visitors" in display_df.columns:
                metrics.append(("New Visitors", "Visitors", "Blues_d"))
            if "Average Session Duration" in display_df.columns:
                metrics.append(("Average Session Duration", "Avg Session (s)", "Blues_d"))
            if "Page Views" in display_df.columns:
                metrics.append(("Page Views", "Page Views", "Blues_d"))
            if "Average Time on page" in display_df.columns:
                metrics.append(("Average Time on page", "Avg Time (s)", "Blues_d"))
            
            # Display visualizations in columns when possible
            if len(metrics) >= 2:
                for i in range(0, len(metrics), 2):
                    col1, col2 = st.columns(2)
                    with col1:
                        if i < len(metrics):
                            plot_improved_graph(display_df, metrics[i][0], metrics[i][1], metrics[i][2])
                    with col2:
                        if i+1 < len(metrics):
                            plot_improved_graph(display_df, metrics[i+1][0], metrics[i+1][1], metrics[i+1][2])
            else:
                for metric in metrics:
                    plot_improved_graph(display_df, metric[0], metric[1], metric[2])
            
            # PDF Export
            if all_figures:
                pdf_buffer = export_plots_to_pdf(all_figures)
                st.markdown("### Download Complete Report")
                st.markdown(get_pdf_download_link(pdf_buffer), unsafe_allow_html=True)