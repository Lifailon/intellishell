import os
import subprocess
import signal
import time
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML

class HistoryCompleter(Completer):
    def __init__(self, history):
        self.history = history

    def get_completions(self, document, complete_event):
        text = document.text.lower()

        if not text:
            return

        if text.startswith('cd '):
            text_suffix = text[2:].strip()

            if text_suffix.startswith('/'):
                path_to_complete = text_suffix
            else:
                path_to_complete = os.path.join(os.getcwd(), text_suffix)

            def get_directories(path):
                try:
                    return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                except FileNotFoundError:
                    return []

            if text_suffix.endswith('/'):
                dirs = get_directories(path_to_complete)
                for d in dirs:
                    full_path = os.path.join(path_to_complete, d)
                    yield Completion(f'cd {full_path}', start_position=-len(text), display=HTML(f'<green>{d}</green>'))
            else:
                base_path = os.path.dirname(path_to_complete)
                partial_name = os.path.basename(path_to_complete)
                dirs = get_directories(base_path)
                for d in dirs:
                    if d.startswith(partial_name):
                        full_path = os.path.join(base_path, d)
                        yield Completion(f'cd {full_path}', start_position=-len(text), display=HTML(f'<green>{d}</green>'))
        else:
            words = text.split()
            for entry in self.history:
                if all(word in entry.lower() for word in words):
                    yield Completion(entry, start_position=-len(text))

def add_to_history(cmd, history, history_file):
    if cmd not in history:
        history.append(cmd)
        with open(history_file, 'a') as f:
            f.write(cmd + '\n')

def main():
    history_file = os.path.expanduser('~/.bash_history')
    if not os.path.exists(history_file):
        print(f"Command history file not found: {history_file}")
        return

    with open(history_file, 'r') as f:
        history = f.read().splitlines()
    history = list(set([entry.strip() for entry in history if entry.strip()]))

    session_history = InMemoryHistory()
    completer = HistoryCompleter(history)

    # Запускаем командный интерпретатор в фоновом режиме
    process = subprocess.Popen('/bin/bash', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)

    while True:
        try:
            current_dir = os.getcwd()
            time_str = "[0.000s]"

            prompt_str = HTML(f'<ansicyan>{current_dir}</ansicyan> <pink>{time_str}</pink> <green> > </green>')

            user_input = prompt(
                prompt_str,
                completer=completer,
                history=session_history
            )

            if user_input.lower() == 'exit':
                process.stdin.write('exit\n')
                process.stdin.flush()
                break

            if user_input:
                add_to_history(user_input, history, history_file)
                process.stdin.write(user_input + '\n')
                process.stdin.flush()

                # Чтение вывода команды
                output = process.stdout.readline()
                while output:
                    print(output, end='')
                    output = process.stdout.readline()

                completer = HistoryCompleter(history)

        except EOFError:
            break
        except KeyboardInterrupt:
            continue

    process.terminate()
    process.wait()

main()
