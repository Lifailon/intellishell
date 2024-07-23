<h1 align="center">
  🧠 Intelli Shell 🐚
</h1>

<p align="center">
<a href="https://github.com/Lifailon/intellishell"><img title="GitHub top language"src="https://img.shields.io/github/languages/top/Lifailon/intellishell?logo=Python&color=blue&"></a>
<a href="https://github.com/Lifailon/intellishell"><img title="GitHub Release"src="https://img.shields.io/github/v/release/Lifailon/intellishell?include_prereleases&logo=Git&color=red&)](https://github.com/Lifailon/intellishell"></a>
<a href="LICENSE"><img title="GitHub License"src="https://img.shields.io/github/license/Lifailon/intellishell?link=https%3A%2F%2Fgithub.com%2FLifailon%2Fintellishell%2Fblob%2Frsa%2FLICENSE&logo=GitHub&color=white&"></a>
</p>

<p align="center">
    <img src="logo/insh.png">
</p>

This is a handler that runs on top of the `Bash` shell and implements an auto-completion mechanism using a dropdown list.

You can view the history of executed commands with support for filtering and regular expressions in real time by selecting and executing them from a list, and use directory navigation without leaving the current input line.

In addition, searching for executable commands and displaying hints for them via [cheat.sh](https://github.com/chubin/cheat.sh) is supported.

---

### ✨ Implemented:

- [x] History filtering (takes into account the order of execution with duplicates excluded) and running the selected command (using the `Enter` button) from a drop-down list in an *external process* with support for recording executed commands in the history.
- [X] Support for regular expressions during filtering, taking into account the position of entered phrases in the command using the `^` character at the beginning or end of a line (by default, the search is performed regardless of the position of entered phrases separated by a space).
- [x] Navigation through directories using `cd` and selecting files for reading via `cat`, `nano`, `vim` and `mcedit`, as well as copying via `cp` and `mv`.
- [x] Captures and displays the execution time of the last executed command in the spirit of `oh-my-bash`.
- [X] A mechanism for storing and passing variables of the current process to an external executable process has been implemented (⚠️ **may work unstable**), and also output of all variables via the `$$` symbol is supported.
- [ ] Auto-complete search for executable commands using the ! or output cheat sheets for the last command entered in the line.

> 💡 Because execution occurs in external and independent processes for each individual command, some actions may not perform as you expect (for example, calling functions repeatedly is not supported).

### ⌨️ Hotkeys:

- `right` – select a command without executing it, which is convenient for continuing recording or moving to the next directory to quickly display its contents.
- `backspace` - updates history to reflect changes.
- `ctrl+c` - clears the current input line (buffer) without moving to a new line or ends the execution of the command being executed
- `ctrl+l` - completely clears the output console and does not affect the input line
- `ctrl+q` - hides the drop-down list until the next input