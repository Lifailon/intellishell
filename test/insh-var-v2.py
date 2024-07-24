import os
import subprocess
import signal
import time
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML

# Глобальная переменная для хранения вывода последней команды
last_command_output = ""

# Словарь для хранения переменных
shell_variables = {}

class HistoryCompleter(Completer):
    def __init__(self, history):
        self.history = history

    def get_completions(self, document, complete_event):
        text = document.text.lower()

        if not text:
            return
        
        if text.startswith('@'):
            # Обработка символа '@'
            search_text = text[1:].lower()
            lines = last_command_output.split('\n')
            for line in lines:
                if search_text in line.lower():
                    yield Completion(line, start_position=-len(text))
        elif text.startswith('cd '):
            # Логика автодополнения для команды cd
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
            # Фильтрация истории команд по введенному тексту
            words = text.split()
            for entry in self.history:
                if all(word in entry.lower() for word in words):
                    yield Completion(entry, start_position=-len(text))

def add_to_history(cmd, history, history_file):
    if cmd not in history:
        history.append(cmd)
        with open(history_file, 'a') as f:
            f.write(cmd + '\n')

def execute_command(cmd, history, history_file):
    global last_command_output, shell_variables
    add_to_history(cmd, history, history_file)
    
    if cmd.startswith('cd '):
        try:
            target_dir = cmd[2:].strip()
            os.chdir(target_dir)
            return 0
        except Exception as e:
            print(f"Incorrect path")
            return 1

    start_time = time.time()
    
    # Обработка присваивания переменных
    if '=' in cmd and not cmd.startswith(('export ', 'declare ')):
        var_name, var_value = cmd.split('=', 1)
        shell_variables[var_name.strip()] = var_value.strip()
        print(f"Variable {var_name.strip()} set to {var_value.strip()}")
        return 0

    # Замена переменных в команде
    for var, value in shell_variables.items():
        cmd = cmd.replace(f"${var}", value)

    try:
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        
        last_command_output = ""
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                last_command_output += output
        
        stderr_output = process.stderr.read()
        if stderr_output:
            print(stderr_output.strip())
            last_command_output += stderr_output
        
        return_code = process.wait()
    except KeyboardInterrupt:
        os.killpg(os.getpgid(process.pid), signal.SIGINT)
        return_code = process.wait()
        print("\nCommand interrupted by user.")
    
    end_time = time.time()
    execution_time = end_time - start_time
    return execution_time

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

    last_execution_time = 0

    while True:
        try:
            current_dir = os.getcwd()
            time_str = f"[{last_execution_time:.3f}s]" if last_execution_time else "[0.000s]"
            prompt_str = HTML(f'<ansicyan>{current_dir}</ansicyan> <pink>{time_str}</pink> <green> > </green>')

            user_input = prompt(
                prompt_str,
                completer=completer,
                history=session_history
            )
            
            if user_input.lower() == 'exit':
                break
            
            if user_input:
                if user_input.startswith('@'):
                    # Поиск по выводу последней команды
                    search_text = user_input[1:].lower()
                    lines = last_command_output.split('\n')
                    for line in lines:
                        if search_text in line.lower():
                            print(line)
                else:
                    last_execution_time = execute_command(user_input, history, history_file)
                completer = HistoryCompleter(history)
        
        except EOFError:
            break

        except KeyboardInterrupt:
            print("\nCommand interrupted by user.")
            continue

main()