import os
import signal
import time
import pexpect
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML
from threading import Thread, Event

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

def read_output(process, stop_event):
    # Функция для чтения вывода процесса в отдельном потоке
    while not stop_event.is_set():  # Продолжаем работу, пока не установлено событие остановки
        try:
            # Читаем данные из процесса без блокировки
            output = process.read_nonblocking(size=1024, timeout=0.1)
            if output:
                # Если есть данные, выводим их на экран
                print(output, end='', flush=True)
        except pexpect.exceptions.TIMEOUT:
            # Игнорируем таймаут, если данные не пришли в течение указанного времени
            pass
        except pexpect.exceptions.EOF:
            # Если процесс завершился, выходим из цикла
            break

def main():
    # Определяем путь к файлу истории команд
    history_file = os.path.expanduser('~/.bash_history')
    if not os.path.exists(history_file):
        # Проверяем, существует ли файл истории команд, если нет, выводим сообщение об ошибке
        print(f"Command history file not found: {history_file}")
        return

    # Читаем историю команд из файла
    with open(history_file, 'r') as f:
        history = f.read().splitlines()

    # Убираем дубликаты и пустые строки из истории команд
    history = list(set([entry.strip() for entry in history if entry.strip()]))

    # Создаем объект истории ввода для автодополнения команд
    session_history = InMemoryHistory()
    # Создаем объект автодополнения, передавая в него историю команд
    completer = HistoryCompleter(history)

    # Запускаем новый процесс Bash с использованием pexpect
    process = pexpect.spawn('/bin/bash', encoding='utf-8', echo=False)

    # Создаем объект события для управления завершением потока вывода
    stop_event = Event()
    # Запускаем поток для чтения вывода процесса
    output_thread = Thread(target=read_output, args=(process, stop_event))
    output_thread.start()

    # Инициализируем переменную для хранения времени выполнения последней команды
    last_execution_time = 0

    while True:
        try:
            # Получаем текущий рабочий каталог
            current_dir = os.getcwd()
            # Формируем строку с временем выполнения последней команды
            time_str = f"[{last_execution_time:.3f}s]" if last_execution_time else "[0.000s]"
    
            # Создаем строку приглашения с цветным форматированием
            prompt_str = HTML(f'<ansicyan>{current_dir}</ansicyan> <pink>{time_str}</pink> <green> > </green>')
    
            # Получаем ввод пользователя с автодополнением и историей команд
            user_input = prompt(
                prompt_str, # Строка приглашения для ввода
                completer=completer, # Объект автодополнения команд
                history=session_history # Объект истории ввода
            )
    
            # Проверяем, если пользователь ввел команду 'exit'
            if user_input.lower() == 'exit':
                # Отправляем команду 'exit' в процесс Bash и прерываем цикл
                process.sendline('exit')
                break
            
            # Если ввод пользователя не пустой
            if user_input:
                # Добавляем команду в историю
                add_to_history(user_input, history, history_file)
    
                # Обрабатываем команду 'cd' для изменения текущего рабочего каталога
                if user_input.startswith('cd '):
                    target_dir = user_input[3:].strip()  # Извлекаем целевую директорию
                    try:
                        os.chdir(target_dir)  # Изменяем текущий рабочий каталог
                    except FileNotFoundError:
                        # Если директория не найдена, выводим сообщение об ошибке
                        print(f"bash: cd: {target_dir}: No such file or directory")
                    continue  # Пропускаем оставшуюся часть цикла и возвращаемся к запросу ввода
                
                # Запускаем выполнение команды
                start_time = time.time()  # Фиксируем время начала выполнения команды
                process.sendline(user_input)  # Отправляем команду в процесс Bash
                process.expect(pexpect.TIMEOUT, timeout=1)  # Ожидаем завершения выполнения команды с таймаутом 1 секунда
    
                end_time = time.time()  # Фиксируем время завершения выполнения команды
                last_execution_time = end_time - start_time  # Рассчитываем время выполнения команды
    
                # Обновляем объект автодополнения с новой историей команд
                completer = HistoryCompleter(history)
    
        except EOFError:
            # Если пользователь завершил ввод (Ctrl+D), выходим из цикла
            break
        except KeyboardInterrupt:
            # Если пользователь прервал выполнение команды (Ctrl+C), отправляем прерывание в процесс Bash
            process.sendintr()
            continue  # Продолжаем выполнение цикла
        
    # Завершаем поток вывода и процесс Bash после выхода из основного цикла
    stop_event.set()  # Устанавливаем событие для завершения потока вывода
    process.terminate()  # Завершаем процесс Bash
    output_thread.join()  # Ожидаем завершения потока вывода

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
