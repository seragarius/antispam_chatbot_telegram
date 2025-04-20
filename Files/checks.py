import telepot
import time
import requests
import re
from urllib.parse import urlparse
from utils import check_spam, get_violations, update_violations, get_username, SAFE_BROWSING_API_KEY, PERSPECTIVE_API_KEY, load_curse_words, check_for_curse_words, logging, muted_users, get_chat_title
from colorama import init, Fore, Style

# Ініціалізація colorama
init()

spam_time_limit = 10
spam_max_messages = 3
timeout_stages = [3600, 21600, 43200]

def resolve_shortened_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=5)
        final_url = response.url
        print(f"{Fore.GREEN}URL розгорнуто:{Style.RESET_ALL} {url} -> {final_url}")
        return final_url
    except requests.RequestException as e:
        print(f"{Fore.RED}Помилка URL:{Style.RESET_ALL} {url} - {e}")
        return url

def is_suspicious_url(url):
    print(f"{Fore.CYAN}Перевірка URL:{Style.RESET_ALL} {url}")
    try:
        api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={SAFE_BROWSING_API_KEY}"
        payload = {
            "client": {"clientId": "SpamBot", "clientVersion": "1.0.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        response = requests.post(api_url, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if "matches" in result and len(result["matches"]) > 0:
                print(f"{Fore.RED}Небезпечний URL:{Style.RESET_ALL} {url} - {result['matches']}")
                return True
            print(f"{Fore.GREEN}Безпечний URL:{Style.RESET_ALL} {url}")
            return False
        else:
            print(f"{Fore.YELLOW}Помилка API:{Style.RESET_ALL} {response.status_code} - {response.text}")
            return True
    except requests.RequestException as e:
        print(f"{Fore.RED}Помилка перевірки:{Style.RESET_ALL} {url} - {e}")
        return True

def extract_urls(text):
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    short_url_pattern = r'(?:[a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/[a-zA-Z0-9]+'
    potential_urls = re.findall(short_url_pattern, text)
    for potential_url in potential_urls:
        if not potential_url.startswith(('http://', 'https://')):
            if any(domain in potential_url for domain in ['bit.ly', 'tinyurl.com', 'goo.gl']):
                urls.append(f"https://{potential_url}")
    return urls

def is_spam_text(text):
    if not text.strip():
        return False
    api_url = f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={PERSPECTIVE_API_KEY}"
    payload = {
        "comment": {"text": text},
        "requestedAttributes": {"SPAM": {}, "TOXICITY": {}},
        "languages": ["en"],
    }
    try:
        response = requests.post(api_url, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            spam_score = result["attributeScores"]["SPAM"]["summaryScore"]["value"]
            toxicity_score = result["attributeScores"]["TOXICITY"]["summaryScore"]["value"]
            print(f"{Fore.CYAN}Perspective API:{Style.RESET_ALL} Текст: '{text}' | SPAM={spam_score:.2f} | TOXICITY={toxicity_score:.2f}")
            return spam_score > 0.75 or toxicity_score > 0.65
        else:
            print(f"{Fore.YELLOW}Помилка Perspective API:{Style.RESET_ALL} {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        print(f"{Fore.RED}Помилка перевірки тексту:{Style.RESET_ALL} '{text}' - {e}")
        return False

def handle_suspicious_links(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    text = msg.get('text', '')
    urls = extract_urls(text)
    if urls:
        for url in urls:
            final_url = resolve_shortened_url(url)
            suspicious = is_suspicious_url(final_url)
            print(f"{Fore.CYAN}Аналіз:{Style.RESET_ALL} Текст: '{text}' | URL: {final_url} | Підозрілий: {Fore.RED if suspicious else Fore.GREEN}{'Так' if suspicious else 'Ні'}{Style.RESET_ALL}")
            if suspicious:
                try:
                    bot.deleteMessage((chat_id, msg['message_id']))
                    print(f"{Fore.YELLOW}Повідомлення видалено:{Style.RESET_ALL} {msg['message_id']}")
                except Exception as e:
                    print(f"{Fore.RED}Помилка видалення:{Style.RESET_ALL} {e}")

                violations = get_violations(user_id)
                update_violations(user_id)
                timeout = timeout_stages[violations] if violations < len(timeout_stages) else timeout_stages[-1]

                if not is_admin(bot, chat_id, user_id) and not is_user_muted(bot, chat_id, user_id):
                    try:
                        bot.restrictChatMember(
                            chat_id, user_id,
                            until_date=int(time.time()) + timeout,
                            can_send_messages=False,
                            can_send_media_messages=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False
                        )
                        muted_users[user_id] = {'chat_id': chat_id, 'until_date': int(time.time()) + timeout}
                        bot.sendMessage(chat_id,
                                        f"🔗 [{get_username(msg)}](tg://user?id={user_id}) отримав таймаут на {timeout // 3600} годин у '{chat_title}' за підозріле посилання: {final_url}!",
                                        parse_mode='Markdown')
                        logging.info(
                            "Suspicious link: User muted",
                            extra={
                                'chat_id': chat_id,
                                'chat_title': chat_title,
                                'user_id': user_id,
                                'username': get_username(msg),
                                'details': f"Message: {text} - URL: {final_url} - Timeout: {timeout // 3600} hours"
                            }
                        )
                    except Exception as e:
                        print(f"{Fore.RED}Помилка обмеження:{Style.RESET_ALL} {e}")
                return True
    else:
        print(f"{Fore.CYAN}Аналіз:{Style.RESET_ALL} Текст: '{text}' | URL: Немає | Підозрілий: {Fore.GREEN}Ні{Style.RESET_ALL}")
    return False


def handle_spam_text(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    text = msg.get('text', '')
    is_spam = is_spam_text(text)
    print(
        f"{Fore.CYAN}Аналіз тексту:{Style.RESET_ALL} '{text}' | Спам/Токсичність: {Fore.RED if is_spam else Fore.GREEN}{'Так' if is_spam else 'Ні'}{Style.RESET_ALL}")

    if is_spam:
        try:
            bot.deleteMessage((chat_id, msg['message_id']))
            print(f"{Fore.YELLOW}Повідомлення видалено:{Style.RESET_ALL} {msg['message_id']}")
        except Exception as e:
            print(f"{Fore.RED}Помилка видалення:{Style.RESET_ALL} {e}")

        violations = get_violations(user_id)
        update_violations(user_id)
        timeout = timeout_stages[violations] if violations < len(timeout_stages) else timeout_stages[-1]

        if not is_admin(bot, chat_id, user_id) and not is_user_muted(bot, chat_id, user_id):
            try:
                bot.restrictChatMember(
                    chat_id, user_id,
                    until_date=int(time.time()) + timeout,
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                )
                muted_users[user_id] = {'chat_id': chat_id, 'until_date': int(time.time()) + timeout}
                bot.sendMessage(chat_id,
                                f"📢 [{get_username(msg)}](tg://user?id={user_id}) отримав таймаут на {timeout // 3600} годин за спам або шкідливий вміст!",
                                parse_mode='Markdown')
                logging.info(
                    "Spam text: User muted",
                    extra={
                        'chat_id': chat_id,
                        'chat_title': chat_title,
                        'user_id': user_id,
                        'username': get_username(msg),
                        'details': f"Message: {text} - Timeout: {timeout // 3600} hours"
                    }
                )
            except Exception as e:
                print(f"{Fore.RED}Помилка обмеження:{Style.RESET_ALL} {e}")
        return True
    return False


def handle_spam(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    text = msg.get('text', '')
    if check_spam(user_id, spam_time_limit, spam_max_messages):
        bot.deleteMessage((chat_id, msg['message_id']))
        violations = get_violations(user_id)
        update_violations(user_id)
        timeout = timeout_stages[violations] if violations < len(timeout_stages) else timeout_stages[-1]

        if not is_admin(bot, chat_id, user_id) and not is_user_muted(bot, chat_id, user_id):
            bot.restrictChatMember(
                chat_id, user_id,
                until_date=int(time.time()) + timeout,
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            muted_users[user_id] = {'chat_id': chat_id, 'until_date': int(time.time()) + timeout}
            bot.sendMessage(chat_id,
                            f"🔇 [{get_username(msg)}](tg://user?id={user_id}) отримав таймаут за спам на {timeout // 3600} годин у '{chat_title}'!",
                            parse_mode='Markdown')
            logging.info(
                "Spam: User muted",
                extra={
                    'chat_id': chat_id,
                    'chat_title': chat_title,
                    'user_id': user_id,
                    'username': get_username(msg),
                    'details': f"Message: {text} - Timeout: {timeout // 3600} hours"
                }
            )
        return True
    return False


def handle_curse_words(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    curse_words = load_curse_words("curse_words.json")
    text = msg.get('text', '').lower()

    if check_for_curse_words(text, curse_words):
        bot.deleteMessage((chat_id, msg['message_id']))
        violations = get_violations(user_id)
        update_violations(user_id)
        timeout = timeout_stages[violations] if violations < len(timeout_stages) else timeout_stages[-1]

        if not is_admin(bot, chat_id, user_id) and not is_user_muted(bot, chat_id, user_id):
            bot.restrictChatMember(
                chat_id, user_id,
                until_date=int(time.time()) + timeout,
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            muted_users[user_id] = {'chat_id': chat_id, 'until_date': int(time.time()) + timeout}
            bot.sendMessage(chat_id,
                            f"🔇 [{get_username(msg)}](tg://user?id={user_id}) отримав таймаут на {timeout // 3600} годин за використання ненормативної лексики!",
                            parse_mode='Markdown')
            logging.info(
                "Curse words: User muted",
                extra={
                    'chat_id': chat_id,
                    'chat_title': chat_title,
                    'user_id': user_id,
                    'username': get_username(msg),
                    'details': f"Message: {text} - Timeout: {timeout // 3600} hours"
                }
            )
        return True
    return False


def is_admin(bot, chat_id, user_id):
    try:
        member = bot.getChatMember(chat_id, user_id)
        return member['status'] in ['administrator', 'creator']
    except telepot.exception.TelegramError as e:
        print(f"{Fore.RED}Помилка при перевірці адміністратора:{Style.RESET_ALL} {e}")
        return False


def is_user_muted(bot, chat_id, user_id):
    try:
        member = bot.getChatMember(chat_id, user_id)
        return member.get('status') == 'restricted' and not member.get('can_send_messages', True)
    except Exception as e:
        print(f"{Fore.RED}Помилка при перевірці статусу користувача:{Style.RESET_ALL} {e}")
        return False