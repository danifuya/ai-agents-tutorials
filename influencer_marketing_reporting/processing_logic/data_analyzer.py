import pandas as pd
import os


def create_campaign_summary(campaign_content_csv_path: str) -> pd.DataFrame | None:
    """Loads campaign content data, processes it, and returns the summary DataFrame."""
    try:
        print(f"Analyzing data from: {campaign_content_csv_path}")
        if not os.path.exists(campaign_content_csv_path):
            print(f"Error: Input file not found at {campaign_content_csv_path}")
            return None

        df_content = pd.read_csv(campaign_content_csv_path)

        # Check if we have the required columns
        required_columns = [
            "campaign_id",
            "influencer_handle",
            "platform",
            "impressions",
            "reach",
            "likes",
            "comments",
        ]
        for col in required_columns:
            if col not in df_content.columns:
                print(f"Error: Required column '{col}' not found in CSV file")
                return None

        # Process data with platform-specific format
        print(f"Processing platform-based format with {len(df_content)} rows")
        return create_platform_campaign_summary(df_content)

    except FileNotFoundError:
        print(f"Error: File not found at {campaign_content_csv_path}")
        return None
    except KeyError as e:
        print(f"Error: Missing expected column in CSV: {e}")
        return None
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback

        traceback.print_exc()
        return None


def create_platform_campaign_summary(df_content: pd.DataFrame) -> pd.DataFrame:
    """Process campaign data with platform-specific data."""
    # Calculate total engagements
    df_content["engagements"] = df_content["likes"].fillna(0) + df_content[
        "comments"
    ].fillna(0)

    # Initialize an empty list to store individual influencer summaries
    all_summaries = []

    # Get unique influencers
    influencers = df_content["influencer_handle"].unique()

    # Process each influencer separately
    for influencer in influencers:
        influencer_data = df_content[df_content["influencer_handle"] == influencer]
        campaign_id = influencer_data["campaign_id"].iloc[0]

        # Base influencer data
        influencer_summary = {
            "campaign_id": campaign_id,
            "influencer_handle": influencer,
            "total_posts": len(influencer_data),
            "total_impressions": influencer_data["impressions"].sum(),
            "total_reach": influencer_data["reach"].sum(),
            "total_engagements": influencer_data["engagements"].sum(),
        }

        # Calculate engagement rate
        if influencer_summary["total_reach"] > 0:
            influencer_summary["avg_engagement_rate"] = round(
                influencer_summary["total_engagements"]
                / influencer_summary["total_reach"],
                4,
            )
        else:
            influencer_summary["avg_engagement_rate"] = 0

        # Add platform-specific metrics
        platforms = ["YouTube", "Instagram", "TikTok"]
        for platform in platforms:
            platform_data = influencer_data[influencer_data["platform"] == platform]

            # If there's data for this platform
            if not platform_data.empty:
                platform_prefix = platform.lower()[:2]
                if platform == "YouTube":
                    platform_prefix = "yt"
                elif platform == "Instagram":
                    platform_prefix = "ig"
                elif platform == "TikTok":
                    platform_prefix = "tt"

                # Add platform-specific data
                influencer_summary[f"{platform_prefix}_posts"] = len(platform_data)
                influencer_summary[f"{platform_prefix}_impressions"] = platform_data[
                    "impressions"
                ].sum()
                influencer_summary[f"{platform_prefix}_reach"] = platform_data[
                    "reach"
                ].sum()

                # Calculate likes_comments
                likes_comments = (
                    platform_data["likes"].sum() + platform_data["comments"].sum()
                )
                influencer_summary[f"{platform_prefix}_likes_comments"] = likes_comments

                # Calculate engagement rate per platform
                if platform_data["reach"].sum() > 0:
                    platform_eng_rate = round(
                        (platform_data["likes"].sum() + platform_data["comments"].sum())
                        / platform_data["reach"].sum(),
                        4,
                    )
                else:
                    platform_eng_rate = 0

                influencer_summary[f"{platform_prefix}_eng_rate"] = platform_eng_rate
            else:
                # Platform not used by this influencer
                if platform == "YouTube":
                    platform_prefix = "yt"
                elif platform == "Instagram":
                    platform_prefix = "ig"
                elif platform == "TikTok":
                    platform_prefix = "tt"

                influencer_summary[f"{platform_prefix}_posts"] = 0
                influencer_summary[f"{platform_prefix}_impressions"] = 0
                influencer_summary[f"{platform_prefix}_reach"] = 0
                influencer_summary[f"{platform_prefix}_likes_comments"] = 0
                influencer_summary[f"{platform_prefix}_eng_rate"] = 0

        # Add this influencer's summary to our list
        all_summaries.append(influencer_summary)

    # Convert list of dictionaries to DataFrame
    summary_df = pd.DataFrame(all_summaries)

    print("Platform-based data analysis complete. Summary generated.")
    return summary_df


