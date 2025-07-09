# E-commerce Data Scraper

This project is a Python-based web scraper designed to extract product information, specifically technical specifications and variants, from e-commerce websites. It uses `crawl4ai` to fetch website content and `pydantic-ai` with OpenAI's GPT models to intelligently extract structured data from the raw HTML.

The scraper is built to be resilient, with capabilities to resume scraping from where it left off and handle errors gracefully by logging them without stopping the entire process.

## Features

- **Intelligent Scraping**: Uses AI to understand and extract product data from markdown content.
- **Dynamic Attribute Handling**: Automatically adjusts to the number of attributes found for each product.
- **Resume Capability**: If the script is interrupted, it can resume from the last processed product, avoiding redundant work.
- **Error Handling**: Logs errors for individual products without halting the entire scraping process.
- **Structured Output**: Generates a clean, structured CSV file with parent-child relationships for product variants.

## Setup

Follow these steps to set up and run the project on your local machine.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create and Activate a Virtual Environment

It is recommended to use a virtual environment to manage project dependencies.

**On macOS and Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

Install all the required Python packages using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

After installing the dependencies, run the `crawl4ai-setup` command to ensure all necessary components for `crawl4ai` are correctly configured.

```bash
crawl4ai-setup
```

### 4. Configure Environment Variables

The scraper uses OpenAI's API to process the scraped data. You will need to provide your API key in an environment file.

Create a file named `.env` in the root of the project directory and add your OpenAI API key as follows:

```
OPENAI_API_KEY="your_openai_api_key_here"
```

Replace `"your_openai_api_key_here"` with your actual OpenAI API key.

Optionally, you can add a `LOGFIRE_TOKEN` to enable agent tracing with Logfire. This can help you monitor and debug the agent's behavior in real-time.

```
LOGFIRE_TOKEN="your_logfire_token_here"
```

## Usage

### 1. Prepare the Input File

The scraper reads a list of product URLs from a CSV file. By default, this file is `products.csv` located in the `ecommerce_data_scrapper` directory.

The CSV file must have the following columns:

- `ID`: A unique identifier for the product.
- `url`: The URL of the product page to scrape.

Here is an example of what `products.csv` might look like:

```csv
ID;url
101;http://example.com/product-a
102;http://example.com/product-b
```

### 2. Run the Scraper

To start the scraping process, run the `main.py` script from the root of the project directory:

```bash
python ecommerce_data_scrapper/main.py
```

The script will process each URL from the input file, scrape the data, and save the results.

### 3. View the Results

The output is saved to `results.csv` inside the `ecommerce_data_scrapper` directory. The file will contain the original data plus the scraped attributes, with a parent-child structure for product variations.
