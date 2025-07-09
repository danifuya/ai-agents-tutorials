import asyncio
import pandas as pd
import os
from typing import Optional, Any, Tuple, Set
from agents.listing_summarizer_agent import (
    listing_summarizer_agent,
)
from crawl4ai import AsyncWebCrawler
import logfire
from dotenv import load_dotenv
from pydantic_ai.usage import UsageLimits
from pydantic_ai import Agent
from utils import process_variants, find_start_attribute_col

load_dotenv()
logfire.configure()
logfire.instrument_pydantic_ai()


async def process_url(url: str) -> Optional[Any]:
    """
    Crawls a given URL using AsyncWebCrawler and then uses an agent
    to extract technical specifications of a product.

    The agent is expected to return a list of product variants with their specs.
    """
    print(f"\nProcessing URL: {url}")
    if not url or not isinstance(url, str) or not url.startswith("http"):
        print(f"Skipping invalid URL: {url}")
        return None

    # Use a web crawler to get the content of the page in markdown format.
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        # Feed the markdown content to an agent to extract structured data.
        especificacion_tecnica_result = await listing_summarizer_agent.run(
            result.markdown, usage_limits=UsageLimits(request_limit=30)
        )
        return especificacion_tecnica_result


def load_data_and_ids(
    input_path: str, output_path: str
) -> Tuple[Optional[pd.DataFrame], Set[str]]:
    """
    Loads the input CSV file into a DataFrame and identifies already processed IDs
    from the output file to allow for resuming the process.
    """
    try:
        # Read IDs as strings to avoid floating point conversion issues.
        df = pd.read_csv(input_path, sep=";", dtype={"ID": str})
        # Sanitize ID column.
        df["ID"] = (
            pd.to_numeric(df["ID"], errors="coerce")
            .astype("Int64")
            .astype(str)
            .replace("<NA>", "")
            .str.strip()
        )
    except FileNotFoundError:
        print(f"Input file not found: {input_path}")
        return None, set()

    processed_ids = set()
    if not os.path.exists(output_path):
        print("No output file found. Starting from scratch.")
        return df, processed_ids

    print(f"Output file found. Attempting to resume from {output_path}.")
    try:
        if os.path.getsize(output_path) > 0:
            # Read only the 'ID' column to avoid parsing errors from
            # inconsistent numbers of columns.
            processed_df = pd.read_csv(output_path, sep=";", usecols=["ID"], dtype=str)

            # Filter out empty/NA IDs which represent child variations.
            valid_ids = processed_df["ID"].dropna().str.strip()
            processed_ids = set(valid_ids[valid_ids != ""])
            print(f"Found {len(processed_ids)} already processed product IDs.")
        else:
            print("Output file is empty. Starting fresh.")

    except (pd.errors.EmptyDataError, ValueError, IOError) as e:
        # ValueError if 'ID' column not found, EmptyDataError for empty file.
        print(f"Could not parse existing results file: {e}. Restarting from scratch.")
        # Overwrite/truncate the problematic file.
        open(output_path, "w").close()
        processed_ids = set()

    return df, processed_ids


async def process_row(row: pd.Series) -> pd.DataFrame:
    """
    Processes a single row from the input DataFrame.
    It scrapes the URL, extracts variants, and returns a new DataFrame with the results.
    """
    current_id = row.get("ID")
    url = row.get("url")

    if pd.isna(url) or not isinstance(url, str) or not url.startswith("http"):
        print(f"ID {current_id} has no valid URL. Keeping original row.")
        return pd.DataFrame([row])

    try:
        spec_result = await process_url(url)

        variants_list = None
        if spec_result and spec_result.output:
            variants_list = spec_result.output

        # `process_variants` will create a new DataFrame with parent and child
        # rows for all the product variants found.
        return process_variants(row, variants_list)
    except Exception as e:
        print(
            f"Error processing URL {url} for ID {current_id}: {e}. Keeping original row with error info."
        )
        # If an error occurs, keep the original row but add error information.
        error_row = row.copy()
        start_col = find_start_attribute_col(error_row)
        error_row[f"Attribute {start_col} name"] = "error:"
        error_row[f"Attribute {start_col} value(s)"] = str(e)
        return pd.DataFrame([error_row])


async def main(
    input_file="products.csv",
    output_file="results.csv",
):
    """
    Main function to orchestrate the scraping process. It loads data,
    iterates through products, scrapes their data, and saves the results.
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    input_file_path = os.path.join(script_dir, input_file)
    output_file_path = os.path.join(script_dir, output_file)

    df, processed_ids = load_data_and_ids(input_file_path, output_file_path)

    if df is None:
        return

    is_first_write = (
        not os.path.exists(output_file_path) or os.path.getsize(output_file_path) == 0
    )

    for index, row in df.iterrows():
        current_id = row.get("ID", "").strip()

        if current_id in processed_ids:
            print(f"Skipping already processed ID: {current_id}")
            continue

        new_data = await process_row(row)

        # Append new data to the CSV file to save progress incrementally.
        new_data.to_csv(
            output_file_path,
            mode="a",
            header=is_first_write,
            sep=";",
            index=False,
            encoding="utf-8-sig",
        )
        if is_first_write:
            is_first_write = False
        print(f"Saved progress for ID {current_id} to {output_file_path}")

        # Add the processed ID to our set to avoid re-processing in the same run.
        if current_id:
            processed_ids.add(current_id)

    print(f"\nProcessing complete. Final results saved to {output_file_path}")


if __name__ == "__main__":
    asyncio.run(main())
