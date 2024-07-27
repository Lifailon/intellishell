#!/usr/bin/env python3

import argparse
import os
import re
import requests
import time
import subprocess
import io
import threading
import signal
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

# Обработка аргументов
parser = argparse.ArgumentParser()
parser.add_argument(
    '--shell',
    type=str,
    default='/bin/bash'
)
args = parser.parse_args()
SHELL = args.shell

# Список команд для обработки автодополнения вывода директорий и файлов
commands = (
    'ls ',
    'cat ',
    'stat ',
    'nano ',
    'vim ',
    'mcedit '
)

# Функция загрузки истории из файла
def load_history(history_file):
    if not os.path.exists(history_file):
        return []
    with open(history_file, 'r') as f:
        # Читаем историю с конца
        reversed_history = reversed(f.read().splitlines())
        # Удаляем дублирующиеся команды с сохранением порядка
        history = list(dict.fromkeys(reversed_history))
    return history

# Функция добавления команды в историю
def add_to_history(cmd, history, history_file):
    # Если команда уже есть в истории, удаляем ее
    if cmd in history:
        history.remove(cmd)
    # Вставляем команду в начало списка истории
    history.insert(0, cmd)
    # Открываем файл истории для записи и перезаписываем команды в обратном порядке
    with open(history_file, 'w') as f:
        for command in reversed(history):
            f.write(command + '\n')

# Функция получения списка директорий
def get_directories(path):
    try:
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    except FileNotFoundError:
        return []

# Функция получения списка директорий и файлов
def get_files_and_dir(path):
    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []

# Функция получения списка команд установленных в системе
def get_exec_commands():
    commands = set()
    # Получаем список всех директорий из переменной PATH
    path_dirs = os.environ.get('PATH', '').split(os.pathsep)
    # Ищем все исполняемые файлы (X_OK) в текущей директории и их подкаталогах
    for directory in path_dirs:
        if os.path.isdir(directory):
            for filename in os.listdir(directory):
                full_path = os.path.join(directory, filename)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    commands.add(filename)
    return sorted(commands)

# Функция получения списка команд через сервис cheat.sh (https://github.com/chubin/cheat.sh)
def get_cheat_commands():
    try:
        sheet_url = "https://cheat.sh/:list"
        response = requests.get(sheet_url)
        response.raise_for_status()
        content = response.text
        lines = content.splitlines()
        commands = [line for line in lines]
        return sorted(commands)
    # Если сервис недоступен, получаем список команд из предыдущей функции
    except requests.RequestException:
        return get_exec_commands()

# Функция подсказок для выпадающего списка
def get_command_examples(command):
    try:
        sheet_url = f"https://cheat.sh/{command}"
        response = requests.get(sheet_url)
        response.raise_for_status()
        content = response.text
        # Разбиваем содержимое на строки
        lines = content.splitlines()
        commands = []
        # Фильтруем вывод
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('#', '---', 'tags:', 'tldr:', 'cheat:')):
                # Удаляем ANSI коды цвета
                line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                # Удаляем лишние комментарии в конце строки
                line = line.split('#', 1)[0].strip()
                # Проверяем, что строка начинается с заданной команды
                if line.startswith(command):
                    commands.append(line)
        return commands
    except requests.RequestException:
        return ["Command not found"]

# Функция подсказок для вывода на экран
def get_print_examples(command):
    command = command.replace(" ", "+")
    sheet_url = f"https://cheat.sh/{command}?Q"
    response = requests.get(sheet_url)
    response.raise_for_status()
    content = response.text
    return print(content)

# Фиксируем список команд при запуске
command_cheat_list = get_cheat_commands()

# Глобальная переменная для хранения вывода последней команды
last_command_output = ""

# Фиксируем переменные окружения при запуске
env = os.environ.copy()

# Функция обновления переменных текущего окружения при соблюдении условий регулярных выражений
def env_update(cmd, env):
    # Фиксируем статус ответа, что переменная не найдена
    updated = "__none__"

    # Регулярное выражение для поиска исполняемых переменных через $()
    dynamic_pattern = re.compile(r'^([^-\s=]+)=\$\((.*?)\)$', re.IGNORECASE)
    matches = dynamic_pattern.findall(cmd)
    # Обновляем переменную с последующем выполнением ее содержимого и повторным обновлением содержимого полученным результатом 
    for var, value in matches:
        # Удаляем $() в начале и конце строки
        cleaned_value = re.sub(r'^\$\(\s*|\s*\)$', '', value)
        env[var] = cleaned_value
        # Возвращаем название (ключ) переменной
        updated = var

    # Регулярное выражение для поиска статических переменных
    static_pattern = re.compile(r'^([^-\s=]+)=([^=\s\`${]{1,}.*)$', re.IGNORECASE)
    matches = static_pattern.findall(cmd)
    # Обновляем переменные с последующим завершением основной функции
    for var, value in matches:
        env[var] = value
        updated = "__static__"

    return updated

# Основной класс обработки автоматического завершения
class HistoryCompleter(Completer):
    def __init__(self, history):
        # Читаем историю команд
        self.history = history

    def get_completions(self, document, complete_event):
        # Фиксируем текущий текст в поле ввода
        text = document.text

        # Ничего не делаем, если текст пустой или содержит только пробелы
        if not text or text.isspace():
            return
        
        # Обработка поиска по содержимому вывода последней исполнямоей команды
        elif text.startswith('@'):
            search_text = text[1:].lower()
            words = search_text.split()  # Разделяем search_text на слова
            lines = last_command_output.split('\n')
            for entry in lines:
                entry_lower = entry.lower()
                if all(word in entry_lower for word in words):
                    yield Completion(
                        entry,
                        start_position=-len(text)
                    )

        # Логика автодополнения для команды cd
        elif text.startswith('cd '):
            # Извлекаем запрос (удаляем команду cd и лишние пробелы по краям)
            text_suffix = text[2:].strip()

            # Определяем путь для автодополнения (абсолютный с корня или относительный текущего каталога)
            if text_suffix.startswith('/'):
                path_to_complete = text_suffix
            else:
                path_to_complete = os.path.join(os.getcwd(), text_suffix)

            # Определяем, нужно ли показывать содержимое директории (/)
            if text_suffix.endswith('/'):
                dirs = get_directories(path_to_complete)
                for d in dirs:
                    full_path = os.path.join(path_to_complete, d)
                    yield Completion(
                        f'cd {full_path}/',
                        start_position = -len(text),
                        display = HTML(f'<green>{d}</green>'),
                        display_meta = 'Directory'
                    )
            # Или использовать автоматическое дополнение
            else:
                base_path = os.path.dirname(path_to_complete)
                partial_name = os.path.basename(path_to_complete)
                dirs = get_directories(base_path)
                for d in dirs:
                    if d.startswith(partial_name):
                        full_path = os.path.join(base_path, d)
                        yield Completion(
                            f'cd {full_path}/',
                            start_position = -len(text),
                            display = HTML(f'<green>{d}</green>'),
                            display_meta = 'Directory'
                        )

        # Логика автодополнения для команды чтения (cat и других)
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
                        yield Completion(
                            f'{command} {full_path}/',
                            start_position = -len(text),
                            display = HTML(f'<green>{entry}</green>'),
                            display_meta = 'Directory'
                        )
                    else:
                        yield Completion(
                            f'{command} {full_path}',
                            start_position = -len(text),
                            display = HTML(f'<cyan>{entry}</cyan>'),
                            display_meta = 'File'
                        )
            else:
                base_path = os.path.dirname(path_to_complete)
                partial_name = os.path.basename(path_to_complete)
                files_and_dirs = get_files_and_dir(base_path)
                for entry in files_and_dirs:
                    if entry.startswith(partial_name):
                        full_path = os.path.join(base_path, entry)
                        if os.path.isdir(full_path):
                            yield Completion(
                                f'{command} {full_path}/',
                                start_position = -len(text),
                                display = HTML(f'<green>{entry}</green>'),
                                display_meta='Directory'
                            )
                        else:
                            yield Completion(
                                f'{command} {full_path}',
                                start_position = -len(text),
                                display = HTML(f'<cyan>{entry}</cyan>'),
                                display_meta = 'File'
                            )

        # Логика автодополнения для команд cp и mv
        elif any(text.startswith(cmd) for cmd in ['cp ', 'mv ']):
            command = text.split()[0]
            # Извлекаем аргументы команды
            arguments = text[len(command):].strip().split()
            
            # Если аргументов меньше двух (еще не указан целевой путь)
            if len(arguments) < 2:
                # Получаем первый аргумент или пустую строку
                text_suffix = arguments[0] if arguments else ''
                if text_suffix.startswith('/'):
                    # Используем абсолютный путь
                    path_to_complete = text_suffix
                else:
                    path_to_complete = os.path.join(os.getcwd(), text_suffix)
                
                # Если путь заканчивается на '/' и не содержит пробелов
                if text_suffix.endswith('/') and ' ' not in text_suffix:
                    files_and_dirs = get_files_and_dir(path_to_complete)
                    for entry in files_and_dirs:
                        full_path = os.path.join(path_to_complete, entry)
                        if os.path.isdir(full_path):
                            # Возвращаем автодополнение для директории
                            yield Completion(
                                f'{command} {full_path}/',
                                start_position = -len(text),
                                display = HTML(f'<green>{entry}/</green>'),
                                display_meta = 'Directory'
                            )
                        else:
                            # Возвращаем автодополнение для файла
                            yield Completion(
                                f'{command} {full_path}',
                                start_position = -len(text),
                                display = HTML(f'<cyan>{entry}</cyan>'),
                                display_meta = 'File'
                            )
                else:
                    base_path = os.path.dirname(path_to_complete)
                    partial_name = os.path.basename(path_to_complete)
                    files_and_dirs = get_files_and_dir(base_path)
                    for entry in files_and_dirs:
                        if entry.startswith(partial_name):
                            full_path = os.path.join(base_path, entry)
                            if os.path.isdir(full_path):
                                yield Completion(
                                    f'{command} {full_path}/',
                                    start_position = -len(text),
                                    display = HTML(f'<green>{entry}/</green>'),
                                    display_meta = 'Directory'
                                )
                            else:
                                yield Completion(
                                    f'{command} {full_path}',
                                    start_position = -len(text),
                                    display = HTML(f'<cyan>{entry}</cyan>'),
                                    display_meta = 'File'
                                )
            
            # Если аргументов два или больше (указан второй путь)
            else:
                second_path_suffix = arguments[-1]
                if second_path_suffix.startswith('/'):
                    path_to_complete = second_path_suffix
                else:
                    path_to_complete = os.path.join(os.getcwd(), second_path_suffix)
                
                # Если второй путь заканчивается на '/' и не содержит пробелов
                if second_path_suffix.endswith('/') and ' ' not in second_path_suffix:
                    files_and_dirs = get_files_and_dir(path_to_complete)
                    for entry in files_and_dirs:
                        full_path = os.path.join(path_to_complete, entry)
                        if os.path.isdir(full_path):
                            yield Completion(
                                f'{command} {" ".join(arguments[:-1])} {full_path}/',
                                start_position = -len(text),
                                display = HTML(f'<green>{entry}/</green>'),
                                display_meta = 'Directory'
                            )
                        else:
                            yield Completion(
                                f'{command} {" ".join(arguments[:-1])} {full_path}',
                                start_position = -len(text),
                                display = HTML(f'<cyan>{entry}</cyan>'),
                                display_meta = 'File'
                            )
                # Обработка второго пути без '/'
                else:
                    base_path = os.path.dirname(path_to_complete)
                    partial_name = os.path.basename(path_to_complete)
                    files_and_dirs = get_files_and_dir(base_path)
                    for entry in files_and_dirs:
                        if entry.startswith(partial_name):
                            full_path = os.path.join(base_path, entry)
                            if os.path.isdir(full_path):
                                yield Completion(
                                    f'{command} {" ".join(arguments[:-1])} {full_path}/',
                                    start_position = -len(text),
                                    display = HTML(f'<green>{entry}/</green>'),
                                    display_meta = 'Directory'
                                )
                            else:
                                yield Completion(
                                    f'{command} {" ".join(arguments[:-1])} {full_path}',
                                    start_position = -len(text),
                                    display = HTML(f'<cyan>{entry}</cyan>'),
                                    display_meta = 'File'
                                )

        # Логика вывода списка переменных через два символа "$" в конце строки
        elif text.split()[-1].startswith('$$'):
            # Забираем текст после последнего символа "$"
            var = text.split('$$')[-1].strip().lower()
            for key in env.keys():
                if key.lower().startswith(var.lower()):
                    yield Completion(f'{key}',
                        start_position = -len(var)-1,
                        display = HTML(f'<cyan>{key}</cyan>'),
                        display_meta = 'Variable'
                    )

        # Логика вывода подсказок, если в начале строки идет "!" проверяем строку целиком
        elif text.startswith('!'):
            cur_text = text[1:].strip().lower().replace(" ","-")
            for command in command_cheat_list:
                command_replace = command.replace("-"," ")
                if command.lower().startswith(cur_text.lower()):
                    yield Completion(f'{command_replace}',
                        start_position = -len(text),
                        display = HTML(f'<cyan>{command_replace}</cyan>'),
                        display_meta = 'Command'
                    )

        # Логика вывода подсказок, если в конце строки идет "!"
        elif text.endswith('!'):
            # Проверяем всю строку
            line = text[:-1].strip().lower().replace(" ","-")
            # Проверяем последнюю команду
            last_command = text[:-1].strip().lower().split(" ")[-1]
            # Проверяем, есть ли строка в массиве доступных команд
            if line in command_cheat_list:
                    line = line.replace("-"," ")
                    examples = get_command_examples(line)
                    for example in examples:
                        if example.lower().startswith(line):
                            if text[-2] == ' ':
                                start_pos = -len(line)-2
                            else:
                                start_pos = -len(line)-1
                            yield Completion(
                                text = example,
                                start_position = start_pos,
                                display_meta = 'Example'
                            )
            # Проверяем, что последняя команда присутствует в массиве команд
            elif last_command in command_cheat_list:
                examples = get_command_examples(last_command)
                for example in examples:
                    if example.lower().startswith(last_command):
                        if text[-2] == ' ':
                            start_pos = -len(last_command)-2
                        else:
                            start_pos = -len(last_command)-1
                        yield Completion(
                            text = example,
                            start_position = start_pos,
                            display_meta = 'Example'
                        )
            # Если примеры не найдены, пытаемся по последней команде выполнить поиск для автоматического завершения
            else:
                cur_text = text.split()[-1][:-1]
                old_text = text.split()[-1]
                for command in command_cheat_list:
                    if command.lower().startswith(cur_text.lower()):
                        yield Completion(f'{command}',
                            start_position = -len(old_text),
                            display = HTML(f'<cyan>{command}</cyan>'),
                            display_meta = 'Command'
                        )
        
        # Если последняя команда в строке ввода содержит текст после символа "!" дополняем ее из списка команд
        elif text.split()[-1].startswith('!'):
            cur_text = text.split()[-1][1:]
            old_text = text.split()[-1]
            for command in command_cheat_list:
                if command.lower().startswith(cur_text.lower()):
                    yield Completion(f'{command}',
                        start_position = -len(old_text),
                        display = HTML(f'<cyan>{command}</cyan>'),
                        display_meta = 'Command'
                    )

        # Фильтрация истории команд по введенному тексту
        else:
            # Опускаем регистр входного значения
            text = text.lower()
            # Фильтрация с использованием Regex для опредиления текст в начале или конце строки с соблюдением положения
            regex_start = text.startswith('^')
            regex_end = text.endswith('^')

            if regex_start:
                # Убираем '^' из начала текста
                text = text[1:]
                for entry in self.history:
                    # Опускаем регистр (lower()) в условии для фильтрации
                    if entry.lower().startswith(text):
                        yield Completion(
                            entry,
                            start_position = -len(document.text)
                        )
                        
            elif regex_end:
                # Убираем '^' из конца текста
                text = text[:-1]
                for entry in self.history:
                    if entry.lower().endswith(text):
                        yield Completion(
                            entry,
                            start_position = -len(document.text)
                        )
            
            # Фильтрация без Regex (проверяем наличие всех словосочетаний в строке не зависимо от их положения)
            else:
                words = text.split()
                for entry in self.history:
                    if all(word in entry.lower() for word in words):
                        yield Completion(
                            entry,
                            start_position = -len(text)
                        )

# Функция выполнения команды
def execute_command(cmd, history, history_file):
    global last_command_output
    # Добавляем команду в историю перед выполнением
    add_to_history(cmd, history, history_file)
    
    # Обработка команды "cd" в текущем процессе Python
    if cmd.startswith('cd '):
        try:
            target_dir = cmd[2:].strip()
            os.chdir(target_dir)
        except Exception as e:
            print(f"Incorrect path")
        return
    
    # Имитируем обработку присвоения переменных
    env_type = env_update(cmd, env)
    
    # Если переменная является статической, обновляем ее в функции и завершаем эту
    if env_type == "__static__":
        return

    # Если переменная динамическая
    elif env_type != "__none__" and env_type != "__static__":
        # Забираем значение переменной по ключу
        value_from_key = env.get(env_type, "")
        if value_from_key:
            try:
                result = subprocess.run(
                    [SHELL, '-c', value_from_key],
                    env=env,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # Забираем вывод успешного выполнения (stdout) и обновляем переменную по ключу
                cleaned_value = result.stdout.strip()
                env[env_type] = cleaned_value
            except subprocess.CalledProcessError as e:
                # В случае ошибки выводим ее на экран
                print(f"Error execut command '{value_from_key}': {e.stderr}")
        return

    # Фиксируем время запуска
    start_time = time.time()

    # Флаг для сигнализации потокам о необходимости завершения
    stop_threads = threading.Event()

    # Создаем буфер для хранения вывода
    output_buffer = io.StringIO()

    # Функция для чтения вывода в отдельном потоке
    def read_output(pipe, buffer):
        try:
            for line in iter(pipe.readline, ''):
                if stop_threads.is_set():
                    break
                print(line, end='', flush=True)
                buffer.write(line)
        # Игнорируем ошибки, связанные с закрытым потоком или буфером
        except (ValueError, IOError):
            pass

    try:
        # Запуск выполнения команды в отдельном процессе с указанием интерпритатора и передачей переменных
        process = subprocess.Popen(
            [SHELL, '-c', cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, 
            env=env,
            preexec_fn=os.setsid,
            bufsize=1
        )
        
        # Запускаем потоки для чтения вывода и ошибок
        stdout_thread = threading.Thread(target=read_output, args=(process.stdout, output_buffer))
        stderr_thread = threading.Thread(target=read_output, args=(process.stderr, output_buffer))
        stdout_thread.start()
        stderr_thread.start()
        
        # Ожидаем завершения процесса
        process.wait()
        
        # Ожидаем завершения потоков чтения
        stdout_thread.join()
        stderr_thread.join()
        
    # Обработка прерывания выполняемого процесса (принудительное завершение)
    except KeyboardInterrupt:
        print("")
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        stop_threads.set()
        process.stdout.close()
        process.stderr.close()
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

    finally:
        # Сохраняем вывод в переменную
        last_command_output = output_buffer.getvalue()
        # Закрываем буфер
        output_buffer.close()

    # Фиксируем время завершения
    end_time = time.time()
    execution_time = end_time - start_time
    return execution_time

# Основная функция
def main():
    # Загружаем историю команд из файла
    history_file = os.path.expanduser('~/.bash_history')
    history = load_history(history_file)
    
    # Создание объекта истории ввода в текущем процессе
    session_history = InMemoryHistory()

    # Создание объекта автодополнения с историей команд
    completer = HistoryCompleter(history)

    # Значение времени выполнения команды по умолчанию при запуске
    last_execution_time = 0

    # Переопределяем действия нажатия клавиш
    bindings = KeyBindings()

    # Обновление вывода автодополнения при удалении текста с помощью Backspace
    @bindings.add('backspace')
    def _(event):
        buffer = event.app.current_buffer
        # Удаляем один симвод перед курсором в текущем буфере ввода
        buffer.delete_before_cursor(1)
        # Запускаем автодополнение по содержимому буфера (аналогично нажатию Tab)
        buffer.start_completion()

    # Выбор команды с помощью стрелочки Right без ее выполнения или для перехода к следующей директории с выводом автодополнения
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
    
    # @bindings.add('c-f')
    # def _(event):
    #     buffer = event.app.current_buffer
    #     buffer.text += '!'
    #     buffer.cursor_position = len(buffer.text)
    #     buffer.start_completion()
    
    @bindings.add('c-q')
    def _(event):
        buffer = event.app.current_buffer
        buffer.cursor_position -= 1
        buffer.cursor_position += 1

    @bindings.add('c-l')
    def _(event):
        os.system('clear')
        event.app.renderer.clear()
        

    @bindings.add('c-c')
    def _(event):
        buffer = event.app.current_buffer
        buffer.reset()

    # Основной цикл обработки
    while True:
        try:
            # Получение текущего рабочего каталога
            current_dir = os.getcwd()

            # Получаем время последнего выполнения команды
            time_str = f"[{last_execution_time:.3f}s]" if last_execution_time else "[0.000s]"

            # Красим строку перед вводом команды
            prompt_str = HTML(f'<ansicyan>{current_dir}</ansicyan> <pink>{time_str}</pink><green> > </green>')

            # Запрос ввода от пользователя с автодополнением
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
                # Если в конце ввода есть два символ "!" отдаем подсказки в выводе
                if user_input.endswith('!!'):
                    line = user_input[:-2].strip().lower()
                    get_print_examples(line)
                    continue

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