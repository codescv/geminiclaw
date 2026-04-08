# Requirements
1. Find the log files in `.gemini/tmp` that have been modified within the last 24 hours.
2. Filter out the new content that occurred within the last 24 hours from the logs.
3. Summarize according to the requirements below, and write results to the corresponding files. Only summarize the requested items; do not write anything else.
4. For any scripts, intermediate results, place them in `projects/memory_update`.

# Progress
Output file: `memory/Progress.md`
What to record: Update the progress of **existing** items in the file.

# Errors
Output file: `memory/Errors.md`
What to record: Record the full command and parameters, time, and error message for any errors (`{"status": "error"}`).