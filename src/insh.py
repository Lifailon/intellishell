import os
import re
import subprocess
import signal
import time
import requests
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import get_app


# Интерпритатор по умолчанию
SHELL = '/bin/bash'

# Список команд для обработки автодополнения вывода списка директорий и файлов
commands = (
    'ls ',
    'cat ',
    'stat ',
    'nano ',
    'vim ',
    'mcedit '
)

# Функция загрузки истории
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

# Функция получения списка команд
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

# Фиксируем переменные системного окружения при запуске
env = os.environ.copy()

# Функция обновления переменных текущего окружения при соблюдении условий регулярных выражений
def env_update(cmd, env):
    # Фиксируем статус ответа, что переменная не найдена
    updated = "__none__"

    # Регулярное выражение для поиска исполняемых переменных через $()
    dynamic_pattern = re.compile(r'^([^-\s=]+)=\$\((.*?)\)$', re.IGNORECASE)
    matches = dynamic_pattern.findall(cmd)
    # Обновляем переменные
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

# Функция подсказок
def get_command_examples(command):
    try:
        sheet_url = f"https://cheat.sh/{command}"
        response = requests.get(sheet_url)
        response.raise_for_status()
        content = response.text
        # Разбиваем содержимое на строки
        lines = content.splitlines()
        # Фильтруем и очищаем строки
        commands = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('#', 'tags:', '---', 'tldr:', 'cheat:')):
                # Удаляем ANSI коды цвета
                line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                # Проверяем, что строка начинается с заданной команды
                if line.startswith(command):
                    commands.append(line)
        return commands
    except requests.RequestException:
        return ["Command not found"]

# Пример использования
# command = "ping"
# examples = get_command_examples(command)
# for example in examples:
#     print(example)

class HistoryCompleter(Completer):
    def __init__(self, history):
        # Читаем историю команд
        self.history = history

    def get_completions(self, document, complete_event):
        # Фиксируем текущий текст в поле ввода
        text = document.text

        # Ничего не делаем, если текст пустой
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

            # Определяем, нужно ли показывать содержимое директории (/) или использовать автоматическое дополнение
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
                            yield Completion(f'{command} {full_path}/', start_position=-len(text), display=HTML(f'<green>{entry}/</green>'), display_meta='Directory')
                        else:
                            # Возвращаем автодополнение для файла
                            yield Completion(f'{command} {full_path}', start_position=-len(text), display=HTML(f'<cyan>{entry}</cyan>'), display_meta='File')
                else:
                    base_path = os.path.dirname(path_to_complete)
                    partial_name = os.path.basename(path_to_complete)
                    files_and_dirs = get_files_and_dir(base_path)
                    for entry in files_and_dirs:
                        if entry.startswith(partial_name):
                            full_path = os.path.join(base_path, entry)
                            if os.path.isdir(full_path):
                                yield Completion(f'{command} {full_path}/', start_position=-len(text), display=HTML(f'<green>{entry}/</green>'), display_meta='Directory')
                            else:
                                yield Completion(f'{command} {full_path}', start_position=-len(text), display=HTML(f'<cyan>{entry}</cyan>'), display_meta='File')
            
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
                            yield Completion(f'{command} {" ".join(arguments[:-1])} {full_path}/', start_position=-len(text), display=HTML(f'<green>{entry}/</green>'), display_meta='Directory')
                        else:
                            yield Completion(f'{command} {" ".join(arguments[:-1])} {full_path}', start_position=-len(text), display=HTML(f'<cyan>{entry}</cyan>'), display_meta='File')
                # Обработка второго пути без '/'
                else:
                    base_path = os.path.dirname(path_to_complete)
                    partial_name = os.path.basename(path_to_complete)
                    files_and_dirs = get_files_and_dir(base_path)
                    for entry in files_and_dirs:
                        if entry.startswith(partial_name):
                            full_path = os.path.join(base_path, entry)
                            if os.path.isdir(full_path):
                                yield Completion(f'{command} {" ".join(arguments[:-1])} {full_path}/', start_position=-len(text), display=HTML(f'<green>{entry}/</green>'), display_meta='Directory')
                            else:
                                yield Completion(f'{command} {" ".join(arguments[:-1])} {full_path}', start_position=-len(text), display=HTML(f'<cyan>{entry}</cyan>'), display_meta='File')

        # Логика автодополнения для поиска исполняемых команд через "!"
        elif text.startswith('!'):
            command_prefix = text[1:].strip().lower()
            self.commands = get_exec_commands()
            for cmd in self.commands:
                if cmd.startswith(command_prefix):
                    yield Completion(cmd, start_position=-len(command_prefix)-1, display=HTML(f'<cyan>{cmd}</cyan>'), display_meta='Command')

        # Логика вывода списка переменных "$" (ищем символ в любой части строки)
        elif '$' in text:
            # Забираем текст после последнего символа "$"
            var = text.split('$')[-1].strip().lower()
            for key in env.keys():
                if key.lower().startswith(var.lower()):
                    yield Completion(f'{key}',
                        start_position=-len(var),
                        display=HTML(f'<cyan>{key}</cyan>'),
                        display_meta='Variable'
                    )

        # Логика вывода подсказок
        elif text.endswith('@'):
            # Удаляем "@" из конца текста
            new_text = text[:-len('@')]
            
            # Получаем доступ к буферу и обновляем текст
            # buffer = get_app().current_buffer
            # cursor_position = buffer.cursor_position
            # cursor_position = len(new_text)
            # Обновляем текст и позицию курсора
            # buffer.text = new_text
            # buffer.cursor_position = cursor_position

            # Получаем примеры команд
            command = new_text.strip().lower()
            examples = get_command_examples(command)
            for example in examples:
                    if example.lower().startswith(command):
                        yield Completion(
                            text=example,
                            start_position=-len(text),
                            display_meta='Example'
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
                        yield Completion(entry, start_position=-len(document.text))
                        
            elif regex_end:
                # Убираем '^' из конца текста
                text = text[:-1]
                for entry in self.history:
                    if entry.lower().endswith(text):
                        yield Completion(entry, start_position=-len(document.text))
            
            # Фильтрация без Regex (проверяем наличие всех словосочетаний в строке не зависимо от их положения)
            else:
                words = text.split()
                for entry in self.history:
                    if all(word in entry.lower() for word in words):
                        yield Completion(entry, start_position=-len(text))
        
# Функция выполнения команды
def execute_command(cmd, history, history_file):
    # Добавляем команду в историю перед выполнением
    add_to_history(cmd, history, history_file)
    
    # Обработка команды 'cd' в текущем процессе Python
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

    # Запуск выполнения команды в отдельном процессе с указанием интерпритатора и передачей переменных
    process = subprocess.Popen(
        [SHELL, '-c', cmd],
        env=env,
        preexec_fn=os.setsid
    )
    
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

# Основная функция
def main():
    # Загружаем историю команд из файла
    history_file = os.path.expanduser('~/.bash_history')
    history = load_history(history_file)
    
    # Создание объекта истории ввода
    session_history = InMemoryHistory()

    # Создание объекта автодополнения с историей команд
    completer = HistoryCompleter(history)

    # Значение времени выполнения команды по умолчанию
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
    
    @bindings.add('c-f')
    def _(event):
        buffer = event.app.current_buffer
        buffer.text += '@'
        buffer.cursor_position = len(buffer.text)
        buffer.start_completion()
    
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