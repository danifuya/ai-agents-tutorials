import os
import sys
import pandas as pd

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from processing_logic.data_analyzer import create_campaign_summary
from processing_logic.report_generator import create_powerpoint_report


def test_platform_campaign_processing():
    """Test the new platform-specific campaign data processing functionality."""
    # Set paths
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    campaign_file = os.path.join(project_root, "data", "campaign.csv")
    summary_output = os.path.join(
        project_root, "reports", "generated_campaign_summary.csv"
    )
    template_file = os.path.join(project_root, "reports", "template", "template.pptx")
    report_output = os.path.join(project_root, "reports", "generated_report.pptx")

    # Ensure directories exist
    os.makedirs(os.path.dirname(summary_output), exist_ok=True)

    # Check if campaign.csv exists
    if not os.path.exists(campaign_file):
        print(f"ERROR: Campaign file not found at {campaign_file}")
        return False

    # Check if template.pptx exists
    if not os.path.exists(template_file):
        print(f"ERROR: Template file not found at {template_file}")
        print("Please ensure template.pptx is in the reports/template directory")
        return False

    print(f"Processing campaign data from {campaign_file}...")

    # Generate the summary CSV
    summary_df = create_campaign_summary(campaign_file)

    if summary_df is None:
        print("ERROR: Failed to generate campaign summary")
        return False

    # Save the summary CSV
    summary_df.to_csv(summary_output, index=False)
    print(f"Summary saved to {summary_output}")

    # Print the platform-specific columns to verify they exist
    platform_cols = [
        col for col in summary_df.columns if col.startswith(("yt_", "ig_", "tt_"))
    ]
    print("\nPlatform-specific columns generated:")
    for col in platform_cols:
        print(f"- {col}")

    # Generate the PowerPoint report
    print(f"\nGenerating PowerPoint report using template {template_file}...")
    result_path = create_powerpoint_report(
        summary_csv_path=summary_output,
        template_pptx_path=template_file,
        output_pptx_path=report_output,
        template_slide_index=1,  # Assuming template is on slide 2
    )

    if result_path:
        print(f"SUCCESS: Report generated at {result_path}")
        return True
    else:
        print("ERROR: Failed to generate PowerPoint report")
        return False


if __name__ == "__main__":
    test_platform_campaign_processing()
