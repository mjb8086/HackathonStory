import streamlit as st
from openai import OpenAI
import base64
import os
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import re

# --- ChatGPT API Configuration ---
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "openai_config.json")


def load_openai_api_key(config_path: str) -> str:
    """Load the OpenAI key from config file or environment variable."""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Warning: Failed to parse {config_path}: {exc}")
        else:
            key = config.get("openai_api_key") or config.get("OPENAI_API_KEY")
            if isinstance(key, str) and key.strip():
                return key.strip()
    # Fallback to environment variable when config file missing or empty
    return os.getenv("OPENAI_API_KEY", "")


OPENAI_API_KEY = load_openai_api_key(CONFIG_FILE)

# Create the OpenAI client only if API key is provided
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(page_title="StoryWorlds", page_icon="📖", layout="centered")
st.title("📖 StoryWorlds: Interactive Adventures")
st.write("Choose your hero, sidekick, and world. Let’s create a magical story together!")

# --- Sidebar for story setup ---
st.sidebar.header("Story Setup")
character = st.sidebar.text_input("Hero (e.g., Alex the Explorer)", "Alex the Explorer")
sidekick = st.sidebar.text_input("Sidekick (e.g., Spark the Dragon)", "Spark the Dragon")
setting = st.sidebar.text_input("Setting (e.g., Magic Forest)", "Magic Forest")

enable_tts = st.sidebar.checkbox("Enable Narration (TTS)", value=False)
enable_images = st.sidebar.checkbox("Enable Illustrations", value=False)

# --- Session state to track story progress ---
if "story_progress" not in st.session_state:
    st.session_state.story_progress = "new story"
if "last_choice" not in st.session_state:
    st.session_state.last_choice = "none"
if "history" not in st.session_state:
    st.session_state.history = []

# --- Function to query GPT for story ---
def generate_story_segment(character, sidekick, setting, progress, choice):
    prompt = f"""
    You are a friendly storytelling assistant for children with autism.
    Create a short, simple, interactive story with gentle social lessons.

    Character: {character}
    Sidekick: {sidekick}
    Setting: {setting}
    Story progress so far: {progress}
    Child's last choice: {choice}

    Output format:
    1. Story Segment (3–4 sentences)
    2. Choices (numbered, simple phrasing, exactly 2 options)
    3. Encouragement/Feedback (1 supportive line)
    """
    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # Replace with gpt-5 if available
        messages=[{"role": "user", "content": prompt}],
        max_tokens=350,
    )
    return response.choices[0].message.content

def extract_choices(story_output):
    # Find the 'Choices' section and extract exactly 2 options
    match = re.search(r"Choices?:\s*(1\..*?)(?:\n2\..*?)(?:\n3\..*?)?", story_output, re.DOTALL)
    if match:
        choices_text = match.group(1)
        # Find all numbered choices
        choices = re.findall(r"\d+\.\s*(.*)", story_output)
        return choices[:2]  # Only return the first 2 choices
    else:
        # Fallback: return generic options
        return ["Option 1", "Option 2"]

# --- Function to generate TTS ---
def generate_tts(text, filename="narration.mp3"):
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text,
    )
    with open(filename, "wb") as f:
        f.write(response.read())
    return filename

# --- Function to generate image ---
def generate_image(prompt):
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="256x256",
        )
        # Debug: Show the full response in the app for troubleshooting
    #    st.info(f"OpenAI image response: {response}")
        # Check for data and URL
        if hasattr(response, 'data') and response.data[0]: #and hasattr(response.data[0], 'url'):
            return f"{response.data[0].url}" 
        else:
            st.warning("Image response did not contain a valid URL. Check your API access and quota.")
            return None
    except Exception as e:
        st.warning(f"Image generation failed: {e}")
        return None

# --- Function to export storybook as PDF ---
def save_story_pdf(story_segments, filename="storybook.pdf"):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 18)
    c.drawString(100, height - 50, "📖 StoryWorlds Adventure")
    c.setFont("Helvetica", 12)
    y = height - 100
    for i, segment in enumerate(story_segments):
        lines = segment.split("\n")
        for line in lines:
            if y < 80:  # new page if space runs out
                c.showPage()
                c.setFont("Helvetica", 12)
                y = height - 80
            c.drawString(50, y, line.strip())
            y -= 18
        y -= 10  # space between segments
    c.save()
    return filename

# --- Generate illustration if enabled ---
if enable_images:
    st.subheader("Illustration")
    img_url = generate_image(f"A children's story illustration of {character} and {sidekick} in {setting}")
    if img_url:
        st.image(img_url, use_container_width=True)
    else:
        st.warning("No image was generated. Please try again, check your API usage, or review the debug info above.")

# --- Display current story ---
st.subheader("Your Story")
story_output = generate_story_segment(
    character, sidekick, setting, st.session_state.story_progress, st.session_state.last_choice
)
st.write(story_output)

# --- Extract choices from story output ---
choices = extract_choices(story_output)

# --- Generate & play TTS if enabled ---
if enable_tts:
    filename = generate_tts(story_output, "narration.mp3")
    if filename:
        with open(filename, "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/mp3")


# --- Capture choice ---
st.subheader("Make a Choice")
choice = st.radio("What should happen next?", choices)

if st.button("Continue Story"):
    st.session_state.last_choice = choice
    st.session_state.story_progress += f"\nChild chose option: {choice}."
    st.session_state.history.append(story_output)
    st.rerun()

# --- Story history viewer ---
with st.expander("📜 Story History"):
    for i, segment in enumerate(st.session_state.history):
        st.markdown(f"**Step {i+1}:**\n{segment}")

# --- Save storybook as PDF ---
if st.session_state.history:
    if st.button("📥 Save Storybook as PDF"):
        pdf_file = save_story_pdf(st.session_state.history)
        with open(pdf_file, "rb") as f:
            st.download_button(
                label="Download My Storybook",
                data=f,
                file_name="storybook.pdf",
                mime="application/pdf"
            )
