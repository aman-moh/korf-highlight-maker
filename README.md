# Korfball YouTube Highlight Maker

## Description

This script downloads a Korfball match video from YouTube, optionally standardizes the video description using the Google Gemini API for better timestamp parsing, finds timestamps associated with specific keywords (e.g., team names, player names, actions like "goal" or "penalty"), extracts video clips around these timestamps, saves each clip individually, and also concatenates them into a final highlight reel. The original downloaded video is kept.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.x is required. You can download it from [python.org](https://www.python.org/downloads/).
2.  **pip:** The Python package installer. It usually comes with Python installations. If not, follow the official [pip installation guide](https://pip.pypa.io/en/stable/installation/).
3.  **FFmpeg:** This is a crucial dependency required by the `moviepy` library for video processing.
    *   FFmpeg must be installed on your system and accessible via the system's PATH environment variable for the script to find it automatically.
    *   Download and install FFmpeg from the official website: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html). Follow the installation instructions specific to your operating system (Windows, macOS, Linux).
    *   **Verification:** After installation, open your terminal or command prompt and type `ffmpeg -version`. If it's installed correctly and in the PATH, you should see version information.
    *   **Alternative Path:** If you install FFmpeg in a non-standard location or prefer not to add it to your system PATH, you can specify the path to the `ffmpeg` executable directly using the `--ffmpeg-path` argument when running the script (see Usage section).
4.  **Google Gemini API Key (Optional but Recommended):**
    *   The script can use the Google Gemini API to automatically standardize the format of the YouTube video description before parsing timestamps. This significantly improves the reliability of timestamp extraction, especially for descriptions with inconsistent formatting.
    *   To use this feature, you need an API key from Google AI Studio: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
    *   You will need to add this key directly into the `highlight_maker.py` script (see Setup section).

## Setup

1.  **Clone the Repository (Optional):**
    If you haven't already, clone the repository to your local machine:
    ```bash
    git clone <repository-url> # Replace <repository-url> with the actual URL
    cd korfball-highlight-maker # Or your project directory name
    ```
    If you already have the files, navigate to the project directory in your terminal.

2.  **Create and Activate a Virtual Environment:**
    It's highly recommended to use a virtual environment to manage project dependencies.

    *   **Create the environment:**
        ```bash
        python -m venv venv
        ```
    *   **Activate the environment:**
        *   On **Linux/macOS**:
            ```bash
            source venv/bin/activate
            ```
        *   On **Windows (Command Prompt/PowerShell)**:
            ```bash
            .\venv\Scripts\activate
            ```
    You should see `(venv)` prefixed to your terminal prompt.

3.  **Install Dependencies:**
    With the virtual environment activated, install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Gemini API Key (Optional):**
    *   Open the `highlight_maker.py` script in a text editor.
    *   Locate the `GEMINI_API_KEY` constant near the top of the file (around line 13).
    *   Replace the placeholder `"YOUR_API_KEY_HERE"` with your actual Google Gemini API key.
        ```python
        # Line 13 (approximately)
        GEMINI_API_KEY = "PASTE_YOUR_REAL_API_KEY_HERE"
        ```
    *   **Security Warning:** Hardcoding API keys directly into source code is generally insecure. Avoid sharing this file or committing it to public version control with your real key inside. If you don't provide a valid key, the script will skip the Gemini standardization step and attempt to parse the raw description directly (which might be less reliable).

## Usage

Run the script from your terminal using the following command structure:

```bash
python highlight_maker.py --url "YOUTUBE_VIDEO_URL" --keywords "Keyword1,Keyword2,..." [--before SECONDS] [--after SECONDS] [--output-dir PATH] [--ffmpeg-path PATH_TO_FFMPEG]
```

**Arguments:**

*   `--url` (Required): The full URL of the YouTube video you want to process.
*   `--keywords` (Required): A comma-separated list of keywords to search for in the video description's timestamps. The search is case-insensitive. Only timestamps matching these keywords will be included in the highlights.
*   `--before` (Optional): The number of seconds to include *before* each matched timestamp in the clip. Default is `5`.
*   `--after` (Optional): The number of seconds to include *after* each matched timestamp in the clip. Default is `10`.
*   `--output-dir` (Optional): The base directory where all output will be saved. Default is `./highlights`. The directory will be created if it doesn't exist.
    *   The final **concatenated highlight video** will be saved directly in this directory (e.g., `./highlights/Video_Title_highlights.mp4`).
    *   **Individual subclips** will be saved in a subdirectory: `./highlights/clips/Video_Title-highlights/`. Each subclip will be named like `Video_Title-Timestamp_Description.mp4`. If multiple clips have the same title and description, a number will be appended (e.g., `_1`, `_2`).
    *   The **original downloaded video** from YouTube will also be kept in the base `--output-dir`.
*   `--ffmpeg-path` (Optional): The explicit file path to the FFmpeg executable. Use this if FFmpeg is not in your system's PATH.

**Gemini Integration:**

*   If you have configured a valid `GEMINI_API_KEY` in the script, it will automatically attempt to standardize the video description using the Gemini API before parsing timestamps.
*   If the `GEMINI_API_KEY` is left as the placeholder or is empty, this step will be skipped, and the script will parse the raw description.

**Example:**

This command downloads the video, looks for timestamps associated with "City" or "Cardiff", creates clips starting 3 seconds before and ending 8 seconds after each timestamp, and saves the final highlight reel to the `./my_korfball_highlights` directory. It will use Gemini for standardization if the API key is configured in the script.

```bash
python highlight_maker.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --keywords "City,Cardiff" --before 3 --after 8 --output-dir "./my_korfball_highlights"
```

## Testing (Optional)

If you want to run the unit tests for this project:

1.  Install the testing framework:
    ```bash
    pip install pytest
    ```
2.  Run the tests from the project root directory:
    ```bash
    pytest