import time
import telepot
import signal
import sys
from dotenv import load_dotenv
import os
from handler import start_bot
from colorama import init, Fore, Style

# Ініціалізація colorama
init()

load_dotenv()
API_TOKEN = os.getenv('TOKEN')
SAFE_BROWSING_API_KEY = os.getenv('SAFE_BROWSING_API_KEY')

if not API_TOKEN or not SAFE_BROWSING_API_KEY:
    print(f"{Fore.RED}Помилка:{Style.RESET_ALL} Токен або Safe Browsing API ключ не знайдено у .env файлі.")
    sys.exit(1)

bot = telepot.Bot(API_TOKEN)

print(f"{Fore.GREEN}Бот працює...{Style.RESET_ALL}")

def graceful_exit(signal, frame):
    print(f"{Fore.YELLOW}Завершення роботи бота...{Style.RESET_ALL}")
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
start_bot(bot)

while True:
    time.sleep(10)