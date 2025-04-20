import sqlite3
import json
import re
from collections import defaultdict
import time
from dotenv import load_dotenv
import os
import logging
from colorama import init, Fore, Style

# Ініціалізація colorama
init()

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] Chat: %(chat_id)s (%(chat_title)s) | User: %(user_id)s (%(username)s) | %(message)s | Details: %(details)s',
    handlers=[
        logging.FileHandler("bot_logs.log"),
        logging.StreamHandler()
    ]
)

# Завантажуємо змінні з .env
load_dotenv()
SAFE_BROWSING_API_KEY = os.getenv('SAFE_BROWSING_API_KEY')
PERSPECTIVE_API_KEY = os.getenv('PERSPECTIVE_API_KEY')

if not SAFE_BROWSING_API_KEY:
    print(f"{Fore.RED}Помилка:{Style.RESET_ALL} Safe Browsing API ключ не знайдено у .env файлі.")
    SAFE_BROWSING_API_KEY = ""
if not PERSPECTIVE_API_KEY:
    print(f"{Fore.RED}Помилка:{Style.RESET_ALL} Perspective API ключ не знайдено у .env файлі.")
    PERSPECTIVE_API_KEY = ""

user_messages = defaultdict(list)
user_last_messages = {}
user_last_reports = {}
muted_users = {}  # Додано для відстеження всіх мутів: {user_id: {'chat_id': chat_id, 'until_date': timestamp}}
curse_words_in_memory = []

class DBConnection:
    def __enter__(self):
        self.conn = sqlite3.connect("violations.db")
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            print(f"{Fore.RED}Помилка при виконанні запиту:{Style.RESET_ALL} {exc_val}")
        self.conn.commit()
        self.conn.close()

def get_chat_title(bot, chat_id):
    try:
        chat = bot.getChat(chat_id)
        return chat.get('title', f"Чат {chat_id}")
    except Exception as e:
        print(f"Помилка отримання назви чату: {e}")
        return f"Чат {chat_id}"

def check_duplicate_messages(user_id, text):
    if user_id in user_last_messages and user_last_messages[user_id] == text:
        return True
    user_last_messages[user_id] = text
    return False

def get_username(msg):
    user = msg.get('from', {})
    username = user.get('username', '')
    first_name = user.get('first_name', '')
    return username if username else first_name if first_name else 'користувач'

def check_spam(user_id, time_limit=10, max_messages=5):
    current_time = time.time()
    user_messages[user_id].append(current_time)
    user_messages[user_id] = [msg_time for msg_time in user_messages[user_id] if current_time - msg_time <= time_limit]
    return len(user_messages[user_id]) > max_messages

def can_report(user_id, report_limit=120):
    current_time = time.time()
    if user_id in user_last_reports:
        last_report_time = user_last_reports[user_id]
        if current_time - last_report_time < report_limit:
            return False
    user_last_reports[user_id] = current_time
    return True

def init_db():
    try:
        with DBConnection() as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS violations (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0
            )''')
    except sqlite3.Error as e:
        print(f"{Fore.RED}Помилка при ініціалізації бази даних:{Style.RESET_ALL} {e}")

def get_violations(user_id):
    try:
        with DBConnection() as cursor:
            cursor.execute("SELECT count FROM violations WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0
    except sqlite3.Error as e:
        print(f"{Fore.RED}Помилка при отриманні порушень для користувача {user_id}:{Style.RESET_ALL} {e}")
        return 0

def update_violations(user_id):
    try:
        with DBConnection() as cursor:
            cursor.execute("INSERT INTO violations (user_id, count) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1", (user_id,))
    except sqlite3.Error as e:
        print(f"{Fore.RED}Помилка при оновленні порушень для користувача {user_id}:{Style.RESET_ALL} {e}")

def decrement_violations(user_id):
    try:
        with DBConnection() as cursor:
            cursor.execute("""
                UPDATE violations
                SET count = CASE
                    WHEN count > 0 THEN count - 1
                    ELSE count
                END
                WHERE user_id = ?
            """, (user_id,))
            if cursor.rowcount == 0:
                print(f"{Fore.YELLOW}Користувач з ID {user_id} не має порушень або не знайдений.{Style.RESET_ALL}")
    except sqlite3.Error as e:
        print(f"{Fore.RED}Помилка при зменшенні порушень для користувача {user_id}:{Style.RESET_ALL} {e}")

def reset_violations(user_id):
    try:
        with DBConnection() as cursor:
            cursor.execute("DELETE FROM violations WHERE user_id = ?", (user_id,))
    except sqlite3.Error as e:
        print(f"{Fore.RED}Помилка при скиданні порушень для користувача {user_id}:{Style.RESET_ALL} {e}")

def add_curse_word(user, word, file_path="curse_words.json"):
    try:
        curse_words = load_curse_words(file_path)
        if curse_words is None:
            return "Не вдалося завантажити список лайливих слів."
        if word.lower() in (w.lower() for w in curse_words):
            return f"Слово '{word}' вже є в списку."
        curse_words.append(word.lower())
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(curse_words, file, ensure_ascii=False, indent=4)
        curse_words_in_memory[:] = curse_words
        return f"Слово '{word}' було успішно додано до списку лайливих слів."
    except Exception as e:
        print(f"{Fore.RED}Помилка при додаванні слова:{Style.RESET_ALL} {e}")
        return "Сталася помилка при додаванні слова."

def load_curse_words(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            curse_words = json.load(file)
            if not isinstance(curse_words, list):
                raise ValueError("Файл повинен містити список слів.")
            return curse_words
    except FileNotFoundError:
        print(f"{Fore.RED}Файл {file_path} не знайдений.{Style.RESET_ALL}")
        return None
    except json.JSONDecodeError:
        print(f"{Fore.RED}Помилка декодування JSON у файлі {file_path}. Перевірте формат файлу.{Style.RESET_ALL}")
        return None
    except ValueError as e:
        print(f"{Fore.RED}Помилка у файлі {file_path}:{Style.RESET_ALL} {e}")
        return None
    except Exception as e:
        print(f"{Fore.RED}Помилка при завантаженні лайливих слів:{Style.RESET_ALL} {e}")
        return None

def check_for_curse_words(phrase, curse_words):
    try:
        phrase = phrase.lower().strip()
        words_in_message = re.findall(r'\b\w+\b', phrase)
        for word in curse_words:
            if word in words_in_message:
                return True
        return False
    except Exception as e:
        print(f"{Fore.RED}Помилка при перевірці фрази на лайливі слова:{Style.RESET_ALL} {e}")
        return False

init_db()