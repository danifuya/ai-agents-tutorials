import pandas as pd
import os

# Removed Pydantic/Pydantic-AI related imports
# from dataclasses import dataclass
# from typing import List
# from pydantic import BaseModel, Field
# from pydantic_ai import Agent, RunContext
# import asyncio
# import nest_asyncio

# --- Removed CampaignMemberSummary BaseModel definition ---
# --- Removed Agent Definition and Dependencies ---


def create_campaign_summary(campaign_content_csv_path: str) -> pd.DataFrame | None:
    """Loads campaign content data, processes it, and returns the summary DataFrame."""
    try:
        print(f"Analyzing data from: {campaign_content_csv_path}")
        if not os.path.exists(campaign_content_csv_path):
            print(f"Error: Input file not found at {campaign_content_csv_path}")
            return None

        df_content = pd.read_csv(campaign_content_csv_path)

        # Check if we have the platform column (new format) and contains expected values
        if (
            "platform" in df_content.columns
            and df_content["platform"].isin(["YouTube", "Instagram", "TikTok"]).any()
        ):
            print(f"Detected new platform-based format with {len(df_content)} rows")
            return create_platform_campaign_summary(df_content)
        else:
            # Original format processing
            print(f"Detected legacy format with {len(df_content)} rows")
            return create_legacy_campaign_summary(df_content)

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


def create_legacy_campaign_summary(df_content: pd.DataFrame) -> pd.DataFrame:
    """Process the original campaign format without platform-specific data."""
    # Calculate total engagements
    like_col = "likes" if "likes" in df_content.columns else None
    comment_col = "comments" if "comments" in df_content.columns else None
    save_col = "saves" if "saves" in df_content.columns else None

    df_content["engagements"] = 0
    if like_col:
        df_content["engagements"] += df_content[like_col].fillna(0)
    if comment_col:
        df_content["engagements"] += df_content[comment_col].fillna(0)
    if save_col:
        df_content["engagements"] += df_content[save_col].fillna(0)

    # Group by campaign and influencer
    summary = (
        df_content.groupby(["campaign_id", "influencer_handle"])
        .agg(
            total_posts=("post_url", "count"),
            total_impressions=("impressions", "sum"),
            total_reach=("reach", "sum"),
            total_engagements=("engagements", "sum"),
        )
        .reset_index()
    )

    # Calculate average engagement rate
    summary["avg_engagement_rate"] = (
        summary["total_engagements"] / summary["total_reach"]
    ).round(4)
    summary.loc[summary["total_reach"] == 0, "avg_engagement_rate"] = 0

    print("Legacy data analysis complete. Summary generated.")
    return summary


def create_platform_campaign_summary(df_content: pd.DataFrame) -> pd.DataFrame:
    """Process the new campaign2 format with platform-specific data."""
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
                platform_prefix = platform.lower()[
                    :2
                ]  # 'yo' for YouTube, 'in' for Instagram, 'ti' for TikTok
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

    print("Platform-based data analysis complete. Extended summary generated.")
    return summary_df


# --- Example Usage (synchronous) ---
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()  # Load .env if running directly

    # Example input/output paths (relative to project root assuming file is in processing_logic)
    project_root = os.path.dirname(os.path.dirname(__file__))  # Get parent directory
    input_csv = os.path.join(project_root, "data", "campaign.csv")
    output_csv = os.path.join(project_root, "reports", "generated_campaign_summary.csv")

    if not os.path.exists(input_csv):
        print(f"ERROR: Example input file not found: {input_csv}")
        print("Please ensure the file exists or modify the path in the __main__ block.")
    else:
        print(f"Running direct analysis function for {input_csv}... (from __main__)")
        df_summary = create_campaign_summary(input_csv)

        if df_summary is not None:
            os.makedirs(os.path.dirname(output_csv), exist_ok=True)
            df_summary.to_csv(output_csv, index=False)
            print(f"Summary saved to {output_csv}")
            print(df_summary)
        else:
            print("Failed to generate summary (from __main__).")
