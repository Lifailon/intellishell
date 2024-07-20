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
        # Фиксируем текущий текст в поле ввода и опускаем регистр
        text = document.text.lower()

        if not text:
            return
        
        # Логика автодополнения для команды cd
        if text.startswith('cd '):
            # Извлекаем запрос (удаляем команду cd и лишние пробелы по краям)
            text_suffix = text[2:].strip()

            # Определяем путь для автодополнения (абсолютный с корня или относительный текущего каталога)
            if text_suffix.startswith('/'):
                path_to_complete = text_suffix
            else:
                path_to_complete = os.path.join(os.getcwd(), text_suffix)

            # Функция для получения списка директорий
            def get_directories(path):
                try:
                    return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                except FileNotFoundError:
                    return []

            # Проверяем, нужно ли показывать содержимое директории или использовать автоматическое дополнение
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
        
        # Фильтрация истории команд по введенному тексту
        else:
            # Поиск в истории по всем словам (проверяем наличие всех слов в строке не зависимо от их положения)
            words = text.split()
            for entry in self.history:
                if all(word in entry.lower() for word in words):
                    yield Completion(entry, start_position=-len(text))
        
# Функция для добавления команды в историю
def add_to_history(cmd, history, history_file):
    if cmd not in history:
        history.append(cmd)
        with open(history_file, 'a') as f:
            # Запись команды в файл истории
            f.write(cmd + '\n')

# Функция для выполнения команды
def execute_command(cmd, history, history_file):
    # Добавляем команду в историю перед выполнением
    add_to_history(cmd, history, history_file)
    
    # Обработка команды 'cd' в текущем процессе
    if cmd.startswith('cd '):
        try:
            target_dir = cmd[2:].strip()
            os.chdir(target_dir)
        except Exception as e:
            print(f"Incorrect path")
        return

    # Фиксируем время запуска
    start_time = time.time()
    # Запуск выполнения команды в отдельном процессе
    process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    
    # Ожидание завершения процесса
    try:
        process.wait()
    # Обработка прерывания выполнения процесса (его принудительное завершение)
    except KeyboardInterrupt:
        print("")
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait()
    
    # Фиксируем время завершения
    end_time = time.time()
    execution_time = end_time - start_time
    return execution_time


def main():
    history_file = os.path.expanduser('~/.bash_history')
    # Проверка, что файл истории команд существует
    if not os.path.exists(history_file):
        print(f"Command history file not found: {history_file}")
        return
    
    # Чтение истории команд из файла
    with open(history_file, 'r') as f:
        history = f.read().splitlines()

    # Удаление пустых строк и дубликатов из истории команд
    history = list(set([entry.strip() for entry in history if entry.strip()]))
    
    # Создание объекта истории ввода
    session_history = InMemoryHistory()
    # Создание объекта автодополнения с историей команд
    completer = HistoryCompleter(history)

    last_execution_time = 0

    while True:
        try:
            # Получение текущего рабочего каталога
            current_dir = os.getcwd()

            # Получаем время последнего выполнения команды
            time_str = f"[{last_execution_time:.3f}s]" if last_execution_time else "[0.000s]"

            # Красим строку перед вводом команды
            prompt_str = HTML(f'<ansicyan>{current_dir}</ansicyan> <pink>{time_str}</pink> <green> > </green>')

            # Запрос ввода от пользователя с автодополнением и историей
            user_input = prompt(
                prompt_str,
                completer=completer,
                history=session_history
            )
            
            # Выход из цикла при вводе 'exit'
            if user_input.lower() == 'exit':
                break
            
            # Выполнение команды
            if user_input:
                # Выполняем команду и получаем время выполнения из вывода функции
                last_execution_time = execute_command(user_input, history, history_file)
                # Обновляем комплитер с новой историей
                completer = HistoryCompleter(history)
        
        # Выход из цикла при завершении (Ctrl+D)
        except EOFError:
            break

        # Продолжение выполнения при прерывании ввода (Ctrl+C)
        except KeyboardInterrupt:
            continue

main()