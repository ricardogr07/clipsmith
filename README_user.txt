clipsmith — AI clip generator for local stream recordings
==========================================================

QUICK START
-----------
1. Open a terminal (Command Prompt or PowerShell) in this folder.

2. Run the setup wizard once to save your API key:

     clipsmith setup

   You'll be asked for your Anthropic (or OpenAI) API key.
   Get one at https://console.anthropic.com  (Anthropic)
               https://platform.openai.com   (OpenAI)

3. Process a recording:

     clipsmith process "C:\path\to\your_recording.mp4"

   Flat 9:16 clips appear in the  out\  folder next to clipsmith.exe.

4. (Optional) Reframe selected clips to stacked layout — webcam on top,
   gameplay on bottom:

     clipsmith reframe <video_id> clip_01 clip_04 clip_09

   Stacked clips are saved to  out\<video_id>\stacked\ .

   Replace <video_id> with the name of the folder created in  work\
   (it matches the filename of your MP4, without the extension).

FIRST-RUN NOTE
--------------
The first time you process a video, clipsmith downloads the transcription
model (~500 MB) to %USERPROFILE%\.cache\huggingface.  This is a one-time
download; subsequent runs use the cached copy.

WEBCAM AUTO-DETECTION
---------------------
clipsmith can automatically find your webcam rectangle in the video using
face detection.  To run it manually:

     clipsmith detect-webcam <video_id>

This prints the detected coordinates and a ready-to-paste snippet for
config.yaml.  Detection also runs automatically during processing if
webcam_rect is not set in config.yaml.

CHANGING SETTINGS
-----------------
Edit config.yaml in this folder.  Common tweaks:

  llm.provider            anthropic  or  openai
  transcribe.model        tiny (fast) | small | medium | large-v3 (accurate)
  clip.max_seconds        maximum clip length (default 30)
  caption.enabled         true  to burn subtitles into every clip
  reframe.webcam_rect     [x, y, w, h] of the webcam box in your source video
  reframe.gameplay_rect   [x, y, w, h] of the gameplay area (stacked mode)
  reframe.split_ratio     fraction of screen height for the webcam panel (0.4 = 40%)

REPROCESSING WITHOUT RE-DOWNLOADING
-------------------------------------
To re-cut clips from an existing run (e.g. after changing caption settings):

     clipsmith clip <video_id>

To re-run from an existing download but redo transcription and LLM:

     clipsmith run-vod --local --skip-download <video_id>

TROUBLESHOOTING
---------------
* "ffmpeg not found"  — make sure ffmpeg.exe is in the same folder as clipsmith.exe.
* "API key" errors    — re-run  clipsmith setup  and paste your key again.
* Slow first run      — transcription model is downloading; wait for it to finish.
* Stacked clips empty — check that reframe.webcam_rect and reframe.gameplay_rect
                        are set in config.yaml, or run  clipsmith detect-webcam.
