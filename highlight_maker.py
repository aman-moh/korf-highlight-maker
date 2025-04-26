import re
import string
import argparse
import yt_dlp
import sys # For error output
import os
import uuid
import google.generativeai as genai # Added for Gemini
from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.config import change_settings
from moviepy.tools import subprocess_call # For potential debugging if needed
from moviepy.config import get_setting # To check ffmpeg path if needed

# --- Configuration ---
# WARNING: Hardcoding API keys is insecure. Replace with your actual key.
# Consider using environment variables or a config file for better security.
GEMINI_API_KEY = "YOUR_API_KEY_HERE"

# --- Gemini Prompt ---
GEMINI_PROMPT_TEMPLATE = """Analyze the following YouTube video description. Your goal is to reformat it so that each line containing a timestamp and description strictly adheres to the format "TIMESTAMP DESCRIPTION".

Instructions:
1. Identify lines that contain a timestamp (like HH:MM:SS or MM:SS) followed by some descriptive text.
2. For these lines, ensure the timestamp appears at the absolute beginning of the line.
3. Place a single space immediately after the timestamp.
4. Append the corresponding description text directly after the single space.
5. Remove any extra characters, symbols (like '-', '–', '—'), or excessive whitespace between the original timestamp and its description.
6. Preserve any lines in the description that *do not* contain timestamps in their original format and relative order.

Example Input Line 1:
   0:15 - Kick-off

Example Output Line 1:
0:15 Kick-off

Example Input Line 2:
(01:23:45) GOAL!!! What a shot!

Example Output Line 2:
01:23:45 GOAL!!! What a shot!

Example Input Line 3:
Check out our sponsor: AwesomeBrand

Example Output Line 3:
Check out our sponsor: AwesomeBrand

Now, please standardize the following YouTube description according to these rules:

--- DESCRIPTION START ---
{description}
--- DESCRIPTION END ---
"""

def standardize_description_with_gemini(description: str, api_key: str) -> str | None:
    """
    Uses the Gemini API to standardize the format of a YouTube description.

    Args:
        description: The raw YouTube video description.
        api_key: The Gemini API key.

    Returns:
        The standardized description string, or None if an error occurs.
    """
    print("\nAttempting to standardize description using Gemini API...")
    try:
        genai.configure(api_key=api_key)
        # Using gemini-1.5-flash-latest as it's generally available and efficient
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        prompt = GEMINI_PROMPT_TEMPLATE.format(description=description)

        # Configure generation parameters (optional, but good practice)
        generation_config = genai.types.GenerationConfig(
            temperature=0.1, # Lower temperature for more deterministic output
            # max_output_tokens=... # Consider setting if descriptions are very long
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            # safety_settings=... # Add safety settings if needed
            )

        # Check if the response has text content
        if response.parts:
            standardized_desc = response.text
            print("Description standardized successfully by Gemini.")
            return standardized_desc
        else:
            # Handle cases where the response might be blocked or empty
            print("Error: Gemini API response was empty or blocked.", file=sys.stderr)
            if hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
            return None

    except Exception as e:
        print(f"Error during Gemini API call: {e}", file=sys.stderr)
        # You might want to check for specific API errors here
        return None


def parse_description_line(line: str) -> tuple[str, str] | None:
    """
    Parses a line to find a timestamp (HH:MM:SS or MM:SS) and description.
    Assumes the line is already standardized by Gemini (or naturally fits the format).

    Args:
        line: The string line to parse.

    Returns:
        A tuple (timestamp_str, description_text) if found, otherwise None.
    """
    # Updated Regex: Expects timestamp at the start, one space, then description.
    # Allows for HH:MM:SS or MM:SS
    match = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s(.+)$", line)
    if match:
        timestamp_str = match.group(1)
        description_text = match.group(2).strip() # Strip potential trailing whitespace
        return timestamp_str, description_text
    # Fallback regex for lines not starting perfectly with timestamp + space
    # This helps if Gemini doesn't format perfectly or if not using Gemini
    match_fallback = re.match(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—\s]*(.+)$", line)
    if match_fallback:
        timestamp_str = match_fallback.group(1)
        description_text = match_fallback.group(2).strip()
        return timestamp_str, description_text

    return None

def convert_timestamp_to_seconds(timestamp_str: str) -> int:
    """
    Converts a timestamp string (HH:MM:SS or MM:SS) to total seconds.

    Args:
        timestamp_str: The timestamp string.

    Returns:
        Total seconds as an integer. Returns 0 for invalid formats.
    """
    parts = timestamp_str.split(':')
    seconds = 0
    try:
        if len(parts) == 3:  # HH:MM:SS
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:  # MM:SS
            seconds = int(parts[0]) * 60 + int(parts[1])
        else:
            # Invalid format based on expected patterns
            return 0
    except ValueError:
        # Handle cases where parts are not integers
        return 0
    return seconds

def filter_timestamps_by_keywords(timestamps: list[tuple[str, str]], keywords: list[str]) -> list[tuple[str, str]]:
    """
    Filters a list of (timestamp, description) tuples based on keywords.

    Args:
        timestamps: List of (timestamp_str, description_text) tuples.
        keywords: List of keywords to search for (case-insensitive).

    Returns:
        A new list containing tuples where the description contains any keyword.
    """
    if not keywords: # If no keywords provided, return the original list or empty? Test implies return all if empty list.
        # Let's return empty list if no keywords, as filtering by nothing means nothing matches.
        # Re-evaluating based on test_filter_no_keywords: it expects the original list back.
         return timestamps # Return original list if keywords list is empty

    filtered_list = []
    lower_keywords = [k.lower() for k in keywords]
    for timestamp_str, description_text in timestamps:
        description_lower = description_text.lower()
        if any(keyword in description_lower for keyword in lower_keywords):
            filtered_list.append((timestamp_str, description_text))
    return filtered_list

def sanitize_filename(filename: str) -> str:
    r"""
    Sanitizes a string to be suitable for use as a filename.

    Removes/replaces invalid characters: / \ : * ? " < > |
    Replaces spaces with underscores.

    Args:
        filename: The original filename string.

    Returns:
        A sanitized filename string.
    """
    # Remove characters invalid in Windows/Unix filenames
    # Define invalid characters for common filesystems
    invalid_chars = r'<>:"/\|?*'
    # Add control characters (0-31)
    invalid_chars += "".join(chr(i) for i in range(32))

    # Replace spaces with underscores first
    sanitized = filename.replace(' ', '_')

    # Remove invalid characters
    sanitized = "".join(char for char in sanitized if char not in invalid_chars)

    # Limit length? Not specified, but often a good idea. Sticking to requirements.
    # Ensure filename is not empty or just dots after sanitization
    if not sanitized or all(c == '.' for c in sanitized):
        return "_invalid_filename_" # Provide a default name if sanitization results in empty/invalid string

    return sanitized


def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Create highlight video from YouTube video based on description timestamps and keywords.")
    parser.add_argument("--url", required=True, help="URL of the YouTube video.")
    parser.add_argument("--keywords", required=True, help="Comma-separated list of keywords to search for in the description.")
    parser.add_argument("--before", type=int, default=5, help="Seconds to include before the timestamp (default: 5).")
    parser.add_argument("--after", type=int, default=10, help="Seconds to include after the timestamp (default: 10).")
    parser.add_argument("--output-dir", default='./highlights', help="Directory to save temporary files and the final video (default: ./highlights).")
    parser.add_argument("--ffmpeg-path", help="Optional path to the ffmpeg executable.")
    # Removed --use-gemini flag
    # TODO: Add validation for 'before' and 'after' (e.g., must be non-negative)
    # TODO: Add validation for keywords format? (e.g., split by comma)
    return parser.parse_args()

def get_video_info(url: str) -> dict | None:
    """
    Fetches video title and description using yt-dlp.

    Args:
        url: The URL of the YouTube video.

    Returns:
        A dictionary {'title': '...', 'description': '...'} on success,
        None on failure.
    """
    ydl_opts = {
        'quiet': True,          # Suppress yt-dlp output
        'skip_download': True,  # Don't download the video itself
        'force_generic_extractor': False, # Use youtube extractor
        'extract_flat': True,   # Don't extract info for playlist entries if it's a playlist URL
        'playlist_items': '0',  # Only process the first item if it's a playlist
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            # Handle potential playlist structure (extract_flat=True helps)
            if 'entries' in info_dict and info_dict['entries']:
                 # If it's a playlist but we got entries (e.g. extract_flat failed?), take the first one
                 video_info = info_dict['entries'][0]
            else:
                 # Assume it's a single video info dict
                 video_info = info_dict

            title = video_info.get('title')
            description = video_info.get('description')

            if title is None or description is None:
                print(f"Error: Could not extract title or description for {url}", file=sys.stderr)
                return None

            return {'title': title, 'description': description}

    except yt_dlp.utils.DownloadError as e:
        print(f"Error fetching video info for {url}: {e}", file=sys.stderr)
        return None
    except Exception as e: # Catch other potential errors
        print(f"An unexpected error occurred while fetching video info: {e}", file=sys.stderr)
        return None


def download_video(url: str, output_dir: str) -> str | None:
    """
    Downloads a video using yt-dlp to a specified directory.

    Args:
        url: The URL of the YouTube video.
        output_dir: The directory where the video should be saved.

    Returns:
        The full path to the downloaded video file on success, None on failure.
    """
    # Generate a unique filename template within the output directory
    # yt-dlp will replace %(ext)s with the actual extension.
    temp_filename_template = os.path.join(output_dir, f"{uuid.uuid4()}.%(ext)s")

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best', # Try to get best combined, fallback to best overall
        'outtmpl': temp_filename_template,    # Output template
        'quiet': False, # Show yt-dlp output for download progress/errors
        'noplaylist': True, # Ensure only single video is downloaded
        # 'verbose': True, # Uncomment for more detailed debugging if needed
    }

    print(f"\nAttempting to download video from {url}...")
    downloaded_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info to get the final filename *after* download
            info_dict = ydl.extract_info(url, download=True) # Set download=True
            # yt-dlp stores the final path in '_filename' after download
            if '_filename' in info_dict and os.path.exists(info_dict['_filename']):
                 downloaded_path = info_dict['_filename']
                 print(f"Video downloaded successfully to: {downloaded_path}")
            else:
                 # Fallback: Scan the directory for the file matching the UUID pattern
                 print("Warning: Could not reliably determine exact download path from yt-dlp info. Trying to find it...")
                 uuid_part = os.path.basename(temp_filename_template).split('.')[0]
                 for filename in os.listdir(output_dir):
                     if filename.startswith(uuid_part):
                         downloaded_path = os.path.join(output_dir, filename)
                         print(f"Found potential match: {downloaded_path}")
                         break
                 if not downloaded_path:
                     print("Error: Download seemed to complete, but couldn't find the output file.", file=sys.stderr)


    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading video: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}", file=sys.stderr)
        return None

    return downloaded_path


# --- Video Processing ---

def process_video(video_path: str, video_title: str, timestamps_with_desc: list[dict], before_sec: int, after_sec: int, output_dir: str, final_output_filename: str, ffmpeg_path: str | None) -> bool:
    """
    Processes the video: extracts subclips based on timestamps, saves them individually,
    concatenates them, and saves the final result.

    Args:
        video_path: Path to the source video file.
        video_title: The sanitized title of the video.
        timestamps_with_desc: A sorted list of dictionaries [{'seconds': int, 'description': str}].
        before_sec: Seconds to include before each timestamp.
        after_sec: Seconds to include after each timestamp.
        output_dir: Base directory for all outputs (e.g., './highlights').
        final_output_filename: Path to save the final concatenated video (e.g., './highlights/video_highlights.mp4').
        ffmpeg_path: Optional path to the ffmpeg executable for moviepy.

    Returns:
        True if processing and writing were successful, False otherwise.
    """
    print(f"\nProcessing video: {video_path}")
    print(f"Outputting final concatenated video to: {final_output_filename}")

    # Create subdirectory for individual clips
    subclips_dir_name = f"{video_title}-highlights"
    subclips_dir = os.path.join(output_dir, "clips", subclips_dir_name)
    try:
        os.makedirs(subclips_dir, exist_ok=True)
        print(f"Ensured subclips directory exists: {subclips_dir}")
    except OSError as e:
        print(f"Error creating subclips directory '{subclips_dir}': {e}", file=sys.stderr)
        return False # Cannot proceed without subclip directory

    if ffmpeg_path:
        try:
            print(f"Attempting to configure moviepy with FFMPEG path: {ffmpeg_path}")
            change_settings({"FFMPEG_BINARY": ffmpeg_path})
        except Exception as e:
            print(f"Warning: Could not configure moviepy with ffmpeg path '{ffmpeg_path}': {e}", file=sys.stderr)

    video = None
    final_clip = None
    clips_for_concat = [] # Keep track of moviepy clip objects for concatenation
    saved_subclip_paths = [] # Keep track of saved file paths if needed later
    subclip_name_counts = {} # To handle duplicate names {base_name: count}

    try:
        video = VideoFileClip(video_path)
        print(f"Video loaded successfully. Duration: {video.duration} seconds.")

        for item in timestamps_with_desc: # Iterate through the list of dicts
            timestamp = item['seconds']
            description = item['description']
            start_time = max(0, timestamp - before_sec)
            end_time = min(video.duration, timestamp + after_sec)

            # Ensure the calculated clip has a positive duration
            if start_time < end_time:
                print(f"  Extracting subclip: {start_time:.2f}s - {end_time:.2f}s (for '{description}')")
                subclip = None # Define subclip here to ensure it's in scope for finally block
                try:
                    subclip = video.subclip(start_time, end_time)
                    clips_for_concat.append(subclip) # Add moviepy object for concatenation

                    # --- Save individual subclip ---
                    sanitized_desc = sanitize_filename(description)
                    base_filename = f"{video_title}-{sanitized_desc}"
                    output_subclip_filename_base = os.path.join(subclips_dir, base_filename)

                    # Handle potential name collisions using the count
                    count = subclip_name_counts.get(base_filename, 0)
                    subclip_name_counts[base_filename] = count + 1 # Increment count for this base name

                    # Determine filename based on count
                    if count == 0:
                        # First occurrence, no suffix needed yet
                        output_subclip_path = f"{output_subclip_filename_base}.mp4"
                    else:
                        # Subsequent occurrences, add suffix like _1, _2 etc.
                        # Note: The count represents how many *previous* clips had the same base name.
                        # So the first duplicate gets _1, second gets _2, etc.
                        output_subclip_path = f"{output_subclip_filename_base}_{count}.mp4"


                    # Check for existence *again* just in case (e.g., if sanitization produced identical names unexpectedly)
                    # This secondary check handles extremely rare edge cases or if the primary count logic fails.
                    suffix_counter = 1
                    original_path_for_retry = output_subclip_path
                    while os.path.exists(output_subclip_path):
                         print(f"    Collision detected (rare): {output_subclip_path} exists. Retrying with suffix.")
                         # Use the original path determined by the count and add another suffix
                         path_parts = os.path.splitext(original_path_for_retry)
                         output_subclip_path = f"{path_parts[0]}_alt{suffix_counter}{path_parts[1]}"
                         suffix_counter += 1


                    print(f"    Saving individual subclip to: {output_subclip_path}")
                    subclip.write_videofile(output_subclip_path, codec="libx264", audio_codec="aac", logger=None) # Suppress logger for subclips
                    saved_subclip_paths.append(output_subclip_path)
                    # --- End save individual subclip ---

                except Exception as e:
                    print(f"  Warning: Failed to extract or save subclip ({start_time:.2f}s - {end_time:.2f}s): {e}", file=sys.stderr)
                    # If extraction failed, subclip might be None, don't append
                    if subclip in clips_for_concat:
                        clips_for_concat.remove(subclip) # Remove if extraction worked but saving failed? Or keep for concat? Let's remove.
            else:
                print(f"  Skipping timestamp {timestamp}s: Calculated start time ({start_time:.2f}s) is not before end time ({end_time:.2f}s).")

        if not clips_for_concat:
            print("No valid video clips could be extracted for concatenation.")
            # We might have saved some clips successfully before an error, but the final concat fails.
            return False # Return False as the main highlight reel cannot be created

        print(f"\nConcatenating {len(clips_for_concat)} clips for the final highlight video...")
        # Using "compose" method is generally safer for clips from the same source
        final_clip = concatenate_videoclips(clips_for_concat, method="compose")

        print(f"Writing final concatenated video to {final_output_filename}...")
        # Use standard codecs for compatibility
        final_clip.write_videofile(final_output_filename, codec="libx264", audio_codec="aac", logger='bar') # Use logger='bar' for progress
        print("Final concatenated video written successfully.")
        return True

    except Exception as e:
        print(f"\nError during video processing: {e}", file=sys.stderr)
        # Add more specific error handling if needed (e.g., file not found, codec issues)
        return False
    finally:
        # Ensure resources are released
        print("Cleaning up video processing resources...")
        if video:
            try:
                video.close()
                print("  Source video clip closed.")
            except Exception as e:
                print(f"  Warning: Error closing source video clip: {e}", file=sys.stderr)
        if final_clip:
            try:
                final_clip.close()
                print("  Final concatenated clip closed.")
            except Exception as e:
                print(f"  Warning: Error closing final clip: {e}", file=sys.stderr)
        # Close the subclips held in memory for concatenation
        # Note: Individual saved subclip files are NOT closed here, they are already written.
        for i, clip in enumerate(clips_for_concat):
             try:
                 clip.close()
             except Exception as e:
                 # print(f"  Warning: Error closing subclip object {i} used for concatenation: {e}", file=sys.stderr)
                 pass # Avoid excessive warnings
        print("Resource cleanup finished.")


# --- File Cleanup ---
# No longer needed as we are keeping the original download
# def cleanup(file_path: str):
#     """Removes the specified file."""
#     print(f"\nAttempting to clean up temporary file: {file_path}")
#     try:
#         os.remove(file_path)
#         print(f"Successfully removed: {file_path}")
#     except FileNotFoundError:
#         print(f"Warning: File not found for cleanup (already deleted?): {file_path}", file=sys.stderr)
#     except OSError as e:
#         print(f"Warning: Error removing file '{file_path}': {e}", file=sys.stderr)
#     except Exception as e:
#         print(f"Warning: An unexpected error occurred during cleanup of '{file_path}': {e}", file=sys.stderr)


def main():
    """Main function to orchestrate the highlight creation process."""
    args = parse_arguments()

    # Ensure base output directory exists
    try:
        os.makedirs(args.output_dir, exist_ok=True)
        print(f"Ensured base output directory exists: {args.output_dir}")
    except OSError as e:
        print(f"Error creating base output directory '{args.output_dir}': {e}", file=sys.stderr)
        sys.exit(1) # Exit if we can't create the output dir

    print("\nArguments parsed:") # Added newline for better spacing
    print(f"  URL: {args.url}")
    print(f"  Keywords: {args.keywords}")
    print(f"  Before: {args.before}")
    print(f"  After: {args.after}")
    print(f"  Output Dir: {args.output_dir}")
    print(f"  FFmpeg Path: {args.ffmpeg_path if args.ffmpeg_path else 'Not specified'}")
    # Removed Gemini flag printout

    # --- Check if API Key Placeholder is still present ---
    use_gemini_processing = False
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_API_KEY_HERE":
        use_gemini_processing = True
        print("  Gemini API Key found in script. Standardization will be attempted.")
    else:
        print("  Gemini API Key is placeholder or empty. Skipping standardization.")


    print("\nFetching video info...")
    video_info = get_video_info(args.url)

    if video_info:
        print("\nVideo Info Fetched:")
        sanitized_title = sanitize_filename(video_info['title']) # Sanitize title once here
        print(f"  Title: {video_info['title']} (Sanitized: {sanitized_title})")
        # Limit description printing for brevity
        raw_description = video_info['description']
        desc_preview = (raw_description[:200] + '...') if len(raw_description) > 200 else raw_description
        print(f"  Description (raw preview):\n{desc_preview}")

        # --- Standardize Description with Gemini (if key is set) ---
        description_to_parse = raw_description
        if use_gemini_processing:
            standardized_desc = standardize_description_with_gemini(raw_description, GEMINI_API_KEY)
            if standardized_desc:
                description_to_parse = standardized_desc
                # Print preview of standardized description
                standardized_preview = (standardized_desc[:200] + '...') if len(standardized_desc) > 200 else standardized_desc
                print(f"\n  Description (standardized preview by Gemini):\n{standardized_preview}")
            else:
                print("\nWarning: Failed to standardize description with Gemini. Attempting to parse the raw description.", file=sys.stderr)
                # Continue with raw description if Gemini fails

        # --- Description Parsing and Filtering ---
        print("\nParsing description for timestamps...")
        all_timestamps = []
        for line in description_to_parse.splitlines(): # Use the potentially standardized description
            parsed = parse_description_line(line)
            if parsed:
                all_timestamps.append(parsed)

        if not all_timestamps:
            print("No timestamps found in the description (after potential standardization).")
            sys.exit(0) # Exit cleanly if no timestamps found
        else:
            print(f"Found {len(all_timestamps)} potential timestamps.")

            print("\nFiltering timestamps by keywords...")
            # Split keywords, strip whitespace, convert to lower, and filter out empty strings
            keywords_list = [k.strip().lower() for k in args.keywords.split(',') if k.strip()]

            if not keywords_list:
                 print("Warning: No keywords provided for filtering. Processing all found timestamps.")
                 filtered_timestamps_tuples = all_timestamps
            else:
                 print(f"Filtering with keywords: {keywords_list}")
                 # Pass the already lowercased keywords list to the filter function
                 # Note: filter_timestamps_by_keywords also does lowercasing, which is slightly redundant but harmless
                 filtered_timestamps_tuples = filter_timestamps_by_keywords(all_timestamps, keywords_list)


            if not filtered_timestamps_tuples:
                print("No timestamps matched the keywords.")
                print("Exiting as no relevant timestamps were found.")
                sys.exit(0) # Clean exit, nothing to do.
            else:
                print(f"Found {len(filtered_timestamps_tuples)} timestamps matching keywords.")

                print("\nConverting filtered timestamps to seconds...")
                filtered_seconds_with_desc = []
                for ts_str, desc_text in filtered_timestamps_tuples:
                    seconds = convert_timestamp_to_seconds(ts_str)
                    # Keep 0-second timestamps, but maybe log if it was invalid? convert_timestamp_to_seconds handles basic invalid cases.
                    filtered_seconds_with_desc.append({'seconds': seconds, 'description': desc_text})

                # Sort by seconds
                filtered_seconds_with_desc.sort(key=lambda x: x['seconds'])

                print("Filtered timestamps (seconds):")
                for item in filtered_seconds_with_desc:
                    print(f"  {item['seconds']}s: {item['description']}")

                # --- Video Downloading ---
                # Download to the base output directory
                downloaded_video_path = download_video(args.url, args.output_dir)

                if downloaded_video_path:
                    print(f"\nVideo download completed: {downloaded_video_path}")
                    # --- Video Processing ---
                    print("\nProceeding with video processing...")
                    # Final concatenated video path remains in the base output directory
                    final_output_path = os.path.join(args.output_dir, f"{sanitized_title}_highlights.mp4")

                    # Pass the list of dicts and title to process_video
                    success = process_video(
                        video_path=downloaded_video_path,
                        video_title=sanitized_title,
                        timestamps_with_desc=filtered_seconds_with_desc,
                        before_sec=args.before,
                        after_sec=args.after,
                        output_dir=args.output_dir, # Pass base output dir
                        final_output_filename=final_output_path,
                        ffmpeg_path=args.ffmpeg_path
                    )

                    if success:
                        print(f"\n✅ Highlight video created successfully: {final_output_path}")
                        print(f"✅ Individual subclips saved in: {os.path.join(args.output_dir, 'clips', f'{sanitized_title}-highlights')}")
                        # --- Cleanup Removed ---
                        # cleanup(downloaded_video_path) # Keep the original download
                    else:
                        print("\n❌ Video processing failed. The final highlight video could not be created.", file=sys.stderr)
                        # --- Cleanup Removed ---
                        # cleanup(downloaded_video_path) # Keep the original download even on failure? Yes.
                        sys.exit(1) # Exit with error if processing fails

                else:
                    print("\nVideo download failed. Cannot proceed with highlight generation.", file=sys.stderr)
                    sys.exit(1) # Exit with error if download fails

    else:
        print("\nFailed to fetch video info. Exiting.")
        sys.exit(1) # Exit with error if info fetch fails


if __name__ == "__main__":
    main()