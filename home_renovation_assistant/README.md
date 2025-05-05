# Home Renovation Assistant

This project is a professional assistant for home renovation planning. It uses Streamlit for the user interface and Pydantic AI for handling the conversation flow and data validation.

## Features

- Professional conversation interface for collecting renovation information
- Structured questionnaire with 15 renovation-related questions
- Image upload for documenting issues and spaces
- Automatic data storage in CSV and JSON formats
- Backend integration for Google Docs export (simulated)
- Professional tone throughout the interaction

## Setup Instructions

### Environment Setup

1. Make sure you have Python 3 installed
2. Create virtual environment (already done):

   ```
   python3 -m venv venv
   ```

3. Activate the virtual environment:

   **On macOS/Linux:**

   ```
   source venv/bin/activate
   ```

   **On Windows:**

   ```
   venv\Scripts\activate
   ```

4. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

5. Create a `.env` file with your OpenAI API key:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### Running the Application

Run the Streamlit app with:

```
streamlit run app.py
```

The application will open in your default web browser.

## Project Structure

- `app.py` - Main Streamlit application with UI and core logic
- `gdocs_export.py` - Backend module for automatic data export
- `requirements.txt` - Project dependencies
- `README.md` - Project documentation
- `images/` - Directory for storing uploaded photos (created at runtime)
- `data/` - Directory for storing conversation data (created at runtime)

## How It Works

1. The client is presented with a professional conversation interface
2. The assistant asks a series of 15 questions about renovation needs
3. After each answer, clients can upload an image related to the question
4. All responses and images are stored in the backend automatically
5. Data is automatically saved in CSV and JSON formats
6. A Google Docs document would be generated in a real implementation
7. The client receives a confirmation message upon completion
8. Company staff can access the stored data for follow-up

## Integration Notes

- In a production environment, the Google Docs API would be fully implemented
- Files would be stored in a more secure location or cloud storage
- The assistant could be extended to include client contact information
- Email notifications could be implemented for new submissions
