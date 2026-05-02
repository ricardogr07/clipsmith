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

   Clips appear in the  out\  folder next to where you ran the command.

FIRST-RUN NOTE
--------------
The first time you process a video, clipsmith downloads the transcription
model (~500 MB) to %USERPROFILE%\.cache\huggingface.  This is a one-time
download; subsequent runs use the cached copy.

CHANGING SETTINGS
-----------------
Edit config.yaml in this folder.  Common tweaks:

  llm.provider       anthropic  or  openai
  transcribe.model   tiny (fast) | small | medium | large-v3 (accurate)
  clip.max_seconds   maximum clip length (default 30)

TROUBLESHOOTING
---------------
* "ffmpeg not found" — make sure ffmpeg.exe is in the same folder as clipsmith.exe.
* "API key" errors  — re-run  clipsmith setup  and paste your key again.
* Slow first run    — transcription model is downloading; wait for it to finish.
