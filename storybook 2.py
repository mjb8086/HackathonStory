import streamlit as st
from openai import OpenAI
import base64
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- ChatGPT API Configuration ---
# Your OpenAI API key is set below and used for all OpenAI features.
OPENAI_API_KEY = ''  # <-- Set in line 11

# Create the OpenAI client using the API key from line 11
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
    2. Choices (numbered, simple phrasing)
    3. Encouragement/Feedback (1 supportive line)
    """
    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # Replace with gpt-5 if available
        messages=[{"role": "user", "content": prompt}],
        max_tokens=350,
    )
    return response.choices[0].message.content

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
            size="1024x1024",
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

# --- Helper to extract choices and feedback from story output ---
def parse_story_output(story_output):
    lines = story_output.split('\n')
    story_lines = []
    choices = []
    feedback = ""
    in_choices = False
    for line in lines:
        line = line.strip()
        if line.lower().startswith("choices") or line.startswith("2."):
            in_choices = True
            continue
        if in_choices:
            if line and (line[0].isdigit() and line[1] in ['.', ')']):
                # e.g. "1. Go to the forest" or "2) Help Spark"
                choice_text = line[2:].strip()
                choices.append(choice_text)
            elif line:
                # If not a choice, treat as feedback
                feedback = line
                in_choices = False
        else:
            if line and not line.lower().startswith("output format"):
                story_lines.append(line)
    story_segment = '\n'.join(story_lines)
    return story_segment, choices, feedback

# --- Display full story so far at the top ---
st.subheader("Your Story So Far")
if st.session_state.history:
    for i, segment in enumerate(st.session_state.history):
        st.markdown(f"**Step {i+1}:**\n{segment}")

# --- Display current story ---
st.subheader("Current Story Segment")
story_output = generate_story_segment(
    character, sidekick, setting, st.session_state.story_progress, st.session_state.last_choice
)
story_segment, choices, feedback = parse_story_output(story_output)
st.write(story_segment)
if feedback:
    st.info(feedback)

# --- Generate & play TTS if enabled ---
if enable_tts:
    filename = generate_tts(story_segment, "narration.mp3")
    if filename:
        with open(filename, "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/mp3")

# --- Generate illustration if enabled ---
if enable_images:
    st.subheader("Illustration")
    img_url = generate_image(f"A children's story illustration of {character} and {sidekick} in {setting}")
    if img_url:
        st.image(img_url, use_container_width=True)
    else:
        st.warning("No image was generated. Please try again, check your API usage, or review the debug info above.")

# --- Capture choice ---
st.subheader("Make a Choice")
if choices:
    choice = st.radio("What should happen next?", choices)
else:
    choice = None

if st.button("Continue Story") and choice:
    st.session_state.last_choice = choice
    st.session_state.story_progress += f"\nChild chose: {choice}."
    st.session_state.history.append(f"{story_segment}\n{feedback}")
    st.rerun()

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
