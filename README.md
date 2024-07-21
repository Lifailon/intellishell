<h1 align="center">
  🧠 Intelli Shell 🐚
</h1>

This is a handler that runs on top of the `Bash` shell and implements an auto-completion mechanism using a dropdown list.

You can view the history of commands executed with filtering and regular expressions support in real time, selecting and executing them, and use directory and file navigation without leaving the current input line.

### ✨ Implemented:

- [x] History filtering (takes into account the order of execution with duplicates excluded) and running the selected command (using the `Enter` button) from a drop-down list in an *external process* with support for recording executed commands in the history;
- [x] Navigate through directories with `cd` and output files for reading via `cat`, `nano`, `vim` and `mcedit`, and also copying via `cp` and `mv`;
- [x] Captures and displays the execution time of the last executed command in the spirit of `oh-my-bash`;
- [X] Refreshing the history by using `backspace` keys and selecting a command with the `right` arrow without executing it, which is also convenient for moving to the next directory to quickly display its contents;.
- [X] Support for regular expressions during filtering, taking into account the position of entered phrases in the command using the `^` character at the beginning or end of a line (by default, the search is performed regardless of the position of entered phrases separated by a space);
- [ ] Search for executable commands using the `!`;
- [ ] A mechanism for storing and passing variables of the current process to an external executable process has been implemented (⚠️ **may work unstable**), and also output of all variables via the `$` symbol is supported;
- [ ] Output keys from man or examples from an external service (e.g. [cheat.sh](https://github.com/chubin/cheat.sh)).

> 💡 Since execution occurs in external and independent processes, some commands may not execute as you expect.
