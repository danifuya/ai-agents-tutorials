import os
import streamlit as st
import pandas as pd
from PIL import Image
from pathlib import Path
import datetime
import json
from typing import Optional, List, Dict, Tuple, Union, Any
from pydantic_ai.messages import ModelMessage

# Import agent module
from agent import RenovationAssistantOutput, renovation_agent

# Import Google Docs export functionality
import gdocs_export

# Load environment variables
from dotenv import load_dotenv

# --- Constants ---
MIN_QUESTIONS_FOR_COMPLETION = 2
# ---------------

load_dotenv()

# Check if Google Drive Folder ID is set
if not os.getenv("GOOGLE_DRIVE_FOLDER_ID"):
    st.warning(
        "GOOGLE_DRIVE_FOLDER_ID environment variable is not set. Google Docs export will be disabled."
    )


# Configure page
st.set_page_config(
    page_title="Home Renovation Assistant", page_icon="🏠", layout="wide"
)


# Type definitions for session state
# class SessionState:
#     messages: List[ModelMessage]
#     collected_data: List[Tuple[str, str, Optional[str]]]  # (question, answer, img_path)
#     uploaded_images: Dict[str, str]  # Maps questions to image paths
#     session_completed: bool
#     current_question: str
#     question_count: int


# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []  # Store ModelMessage objects directly
if "collected_data" not in st.session_state:
    st.session_state.collected_data = []
if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = {}
if "session_completed" not in st.session_state:
    st.session_state.session_completed = False
if "current_question" not in st.session_state:
    st.session_state.current_question = ""
if "question_count" not in st.session_state:
    st.session_state.question_count = 0


def save_session_data():
    """Save the collected session data to CSV and JSON formats."""
    if not st.session_state.collected_data:
        return False

    # Create a timestamp for the filenames
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create data directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)

    # Save as CSV
    data = []
    for question, answer, _ in st.session_state.collected_data:
        data.append({"Question": question, "Answer": answer})

    df = pd.DataFrame(data)
    csv_filename = f"data/renovation_assistant_{timestamp}.csv"
    df.to_csv(csv_filename, index=False)

    # Save as JSON for Google Docs integration
    gdocs_export.export_to_json(
        st.session_state.collected_data, f"data/renovation_assistant_{timestamp}.json"
    )

    # Generate Google Docs URL
    gdocs_url = gdocs_export.export_to_gdocs(st.session_state.collected_data)
    if gdocs_url:
        st.session_state.gdocs_url = gdocs_url  # Store for potential display
        print(f"Google Doc created: {gdocs_url}")
    else:
        print("Failed to export to Google Docs.")

    return True


def handle_next_question():
    """Get the next question from the agent and update session state."""
    question_count = st.session_state.question_count
    collected_data = st.session_state.collected_data if question_count > 0 else None
    messages = st.session_state.messages

    # Determine the prompt based on the turn number
    if question_count == 0:
        # First interaction with an initial prompt
        prompt = "Hi there, I'd like to perform a home renovation."
        message_history = []
    else:
        # For subsequent questions, use the last user answer as the prompt
        # and all previous messages as message history
        _, last_answer, _ = collected_data[-1]
        prompt = last_answer
        message_history = messages if messages else []

    # Run the agent with proper message history
    result = renovation_agent.run_sync(
        user_prompt=prompt,
        message_history=message_history,
    )

    # Get agent response
    response = result.output

    # Check if the assessment is complete (requires >= MIN_QUESTIONS_FOR_COMPLETION questions)
    is_complete = (
        response.is_complete and question_count >= MIN_QUESTIONS_FOR_COMPLETION
    )

    next_question = None

    if not is_complete and response.next_question:
        next_question = response.next_question
    elif question_count < MIN_QUESTIONS_FOR_COMPLETION:
        # Force another question if we haven't asked the minimum yet
        forceful_prompt = f"We need at least {MIN_QUESTIONS_FOR_COMPLETION} questions total. You've only asked {question_count} so far. Please provide the next question now. Do not number the question."

        # Re-run the agent with the forceful prompt and same message history
        result = renovation_agent.run_sync(
            user_prompt=forceful_prompt,
            message_history=message_history,
        )

        response = result.output
        next_question = (
            response.next_question
            if response.next_question
            else "Is there anything else about your renovation needs that you'd like to share?"
        )
        is_complete = False
    else:
        # If we've asked MIN_QUESTIONS_FOR_COMPLETION+ questions and the agent says complete
        next_question = None
        is_complete = True

    # Store all messages for next run
    st.session_state.messages = result.all_messages()

    if is_complete:
        st.session_state.current_question = None
        st.session_state.session_completed = True
        return True
    elif next_question:
        st.session_state.current_question = next_question
        st.session_state.question_count += 1
        return False

    return False


def main():
    st.title("🏠 Home Renovation Assistant")

    # Debug section
    with st.expander("Debug Information"):
        st.subheader("Session State Messages")

        st.subheader("Other Session State Variables")
        st.write(f"Number of questions asked: {st.session_state.question_count}")
        st.write(f"Current question: {st.session_state.current_question}")
        st.write(f"Session completed: {st.session_state.session_completed}")
        st.write(
            f"Number of collected data entries: {len(st.session_state.collected_data)}"
        )

    # Sidebar for company branding/info
    with st.sidebar:
        st.header("Company Information")
        st.write(
            "Thank you for choosing our renovation services. This assistant will help us understand your needs better."
        )
        st.write(
            "All information provided will be kept confidential and used only for planning your renovation project."
        )
        st.write("---")
        st.write("**Contact Information:**")
        st.write("Phone: (555) 123-4567")
        st.write("Email: info@renovationcompany.com")

        if st.session_state.collected_data:
            st.write("---")
            st.write(f"Questions asked: {st.session_state.question_count}")

    # Main content area
    if not st.session_state.session_completed:
        st.header("Please tell us about your renovation project")
        st.write(
            "Answer the following questions to help us understand your renovation needs."
        )

        # Display conversation history
        for q, a, img_path in st.session_state.collected_data:
            with st.chat_message("assistant"):
                st.write(q)
            with st.chat_message("user"):
                st.write(a)
                if img_path:
                    st.image(img_path, width=300)

        # Handle current interaction
        if (
            not st.session_state.current_question
            and not st.session_state.session_completed
        ):
            # Show typing placeholder
            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.write("Typing...")

            # Get the next question
            is_complete = handle_next_question()

            if is_complete:
                placeholder.empty()
                save_session_data()
                st.rerun()
            elif st.session_state.current_question:
                placeholder.write(st.session_state.current_question)
            else:
                placeholder.empty()
        elif st.session_state.current_question:
            with st.chat_message("assistant"):
                st.write(st.session_state.current_question)

        # User response area
        if not st.session_state.session_completed and st.session_state.current_question:
            user_response = st.chat_input("Type your answer here")

            # Image upload
            uploaded_file = st.file_uploader(
                "Upload a relevant photo (optional)",
                type=["jpg", "jpeg", "png"],
                key=f"upload_{st.session_state.question_count}",
            )

            # Button to finish conversation early
            if st.button("Finish Conversation & Generate Report", key="finish_button"):
                if st.session_state.collected_data:  # Only save if there's data
                    print("Finish button clicked, saving data...")
                    if save_session_data():
                        st.session_state.session_completed = True
                        st.session_state.current_question = (
                            ""  # Clear question to prevent loop issues
                        )
                        st.rerun()
                    else:
                        st.warning("Could not save session data.")
                        # Keep session active if save fails
                else:
                    st.info(
                        "No data collected yet. Please answer at least one question before finishing."
                    )
                    # Keep session active

            # Process user response if the button wasn't clicked
            if user_response:
                current_question = st.session_state.current_question

                # Handle image upload
                img_path = None
                if uploaded_file is not None:
                    Path("images").mkdir(exist_ok=True)
                    img_path = f"images/q{st.session_state.question_count}_{uploaded_file.name}"
                    Image.open(uploaded_file).save(img_path)
                    st.session_state.uploaded_images[current_question] = img_path
                elif current_question in st.session_state.uploaded_images:
                    img_path = st.session_state.uploaded_images[current_question]

                # Store conversation data
                st.session_state.collected_data.append(
                    (current_question, user_response, img_path)
                )

                # Clear current question to trigger getting the next one
                st.session_state.current_question = ""
                st.rerun()
    else:
        # Thank you page after session completion
        st.success("Thank you for providing your renovation information!")
        st.header("Your information has been received")
        st.write("""
        Your renovation information has been successfully submitted to our team. 
        A representative will contact you within 1-2 business days to discuss your project in detail.
        
        Thank you for choosing our services for your renovation needs.
        """)

        # Option to start a new session
        if st.button("Start a new conversation"):
            # Reset session state
            st.session_state.messages = []
            st.session_state.collected_data = []
            st.session_state.uploaded_images = {}
            st.session_state.session_completed = False
            st.session_state.current_question = ""
            st.session_state.question_count = 0
            st.rerun()


if __name__ == "__main__":
    main()
