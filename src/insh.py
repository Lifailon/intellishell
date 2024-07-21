import os
import subprocess
import signal
import time
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

# Список команд для обработки автодополнения вывода списка директорий и файлов
commands = (
    'ls ',
    'cat ',
    'stat ',
    'nano ',
    'vim ',
    'mcedit '
)

# Функция для получения списка директорий
def get_directories(path):
    try:
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    except FileNotFoundError:
        return []

# Функция для получения списка файлов и директорий
def get_files_and_dir(path):
    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []

class HistoryCompleter(Completer):
    def __init__(self, history):
        # Читаем историю команд
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

            # Проверяем, нужно ли показывать содержимое директории или использовать автоматическое дополнение
            if text_suffix.endswith('/'):
                dirs = get_directories(path_to_complete)
                for d in dirs:
                    full_path = os.path.join(path_to_complete, d)
                    yield Completion(f'cd {full_path}/', start_position=-len(text), display=HTML(f'<green>{d}</green>'), display_meta='Directory')
            else:
                base_path = os.path.dirname(path_to_complete)
                partial_name = os.path.basename(path_to_complete)
                dirs = get_directories(base_path)
                for d in dirs:
                    if d.startswith(partial_name):
                        full_path = os.path.join(base_path, d)
                        yield Completion(f'cd {full_path}/', start_position=-len(text), display=HTML(f'<green>{d}</green>'), display_meta='Directory')

        # Логика автодополнения для команды чтения
        elif any(text.startswith(cmd) for cmd in commands):
            command = text.split()[0]
            text_suffix = text[len(command):].strip()

            if text_suffix.startswith('/'):
                path_to_complete = text_suffix
            else:
                path_to_complete = os.path.join(os.getcwd(), text_suffix)

            if text_suffix.endswith('/'):
                files_and_dirs = get_files_and_dir(path_to_complete)
                for entry in files_and_dirs:
                    full_path = os.path.join(path_to_complete, entry)
                    if os.path.isdir(full_path):
                        yield Completion(f'{command} {full_path}/', start_position=-len(text), display=HTML(f'<green>{entry}</green>'), display_meta='Directory')
                    else:
                        yield Completion(f'{command} {full_path}', start_position=-len(text), display=HTML(f'<cyan>{entry}</cyan>'), display_meta='File')
            else:
                base_path = os.path.dirname(path_to_complete)
                partial_name = os.path.basename(path_to_complete)
                files_and_dirs = get_files_and_dir(base_path)
                for entry in files_and_dirs:
                    if entry.startswith(partial_name):
                        full_path = os.path.join(base_path, entry)
                        if os.path.isdir(full_path):
                            yield Completion(f'{command} {full_path}/', start_position=-len(text), display=HTML(f'<green>{entry}</green>'), display_meta='Directory')
                        else:
                            yield Completion(f'{command} {full_path}', start_position=-len(text), display=HTML(f'<cyan>{entry}</cyan>'), display_meta='File')
        
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
    # Обработка прерывания выполняемого процесса (принудительное завершение)
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

    # Значение по умолчанию
    last_execution_time = 0

    # Переопределяем действия нажатия клавиш
    bindings = KeyBindings()

    # Обновления вывода автодополнения при удалении текста с помощью Backspace
    @bindings.add('backspace')
    def _(event):
        buffer = event.app.current_buffer
        # Удаляем один симвод перед курсором в текущем буфере ввода
        buffer.delete_before_cursor(1)
        # Запускаем автодополнение по содержимому буфера (аналогично нажатию Tab)
        buffer.start_completion()

    # С помощью Right выбираем команду из списка без ее выполнения и для перехода к следующей директории с выводом автодополнения
    @bindings.add('right')
    def _(event):
        buffer = event.app.current_buffer
        if buffer.cursor_position == len(buffer.text):
            # Перемещаем курсор на одну позицию назад
            buffer.cursor_position -= 1
            # Перемещаем курсор в конец строки
            buffer.cursor_position = len(buffer.text)
            buffer.start_completion()
        else:
            # Перемещаем курсор на одну позицию вперед
            buffer.cursor_position += 1

    while True:
        try:
            # Получение текущего рабочего каталога
            current_dir = os.getcwd()

            # Получаем время последнего выполнения команды
            time_str = f"[{last_execution_time:.3f}s]" if last_execution_time else "[0.000s]"

            # Красим строку перед вводом команды
            prompt_str = HTML(f'<ansicyan>{current_dir}</ansicyan> <pink>{time_str}</pink><green> > </green>')

            # Запрос ввода от пользователя с автодополнением и историей
            user_input = prompt(
                prompt_str,
                completer=completer,
                history=session_history,
                # Передать обработчик нажатий клавиш
                key_bindings=bindings
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