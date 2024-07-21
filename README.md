# Intelli Shell

This is a handler that runs on top of the Bash shell and implements an auto-completion mechanism using a dropdown list.

You can view a filtered history of executed commands with real-time regular expression support by selecting and executing them, and use directory and file navigation without leaving the current input line.

Implemented:
- Filtering by history with running the selected command from the drop-down list in an *external process* with support for recording executed commands in history
- Navigation through directories using cd and outputting files for reading using cat, nano, vim and mcedit
- Records the execution time of the last executed command in the spirit of oh-my-bash
- Update history when using backspace and selecting a command using the Right arrow without executing it or to move to the next directory with auto-completion output.
- Use of regular expressions when filtering, taking into account the position of phrases in the command starting from the beginning or end of the line (by default, the search is performed regardless of the position of the entered phrases separated by a space)
- Search for executable commands using the "!"
- Implemented a mechanism for processing variables of the current process for transmission to executable commands (**may be unstable**) and outputting a list of variables of the current environment.