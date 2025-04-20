import time
import threading
import requests
from utils import load_curse_words, check_for_curse_words, get_username, logging, PERSPECTIVE_API_KEY, get_chat_title
from commands import handle_ban_command, handle_mute_command, handle_unmute_command, handle_add_curse_word_command, handle_report_command, handle_appeal_command
from checks import handle_spam, handle_curse_words, is_admin, is_user_muted, handle_suspicious_links, handle_spam_text
from colorama import init, Fore, Style

# Ініціалізація colorama
init()

rules_interval = 600
rules_thread_started = False
new_user_restrictions = {}

def send_chat_rules(bot, chat_id):
    while True:
        try:
            with open('chat_rules.txt', 'r', encoding='utf-8') as f:
                rules = f.read()
            bot.sendMessage(chat_id, rules)
        except Exception as e:
            print(f"{Fore.RED}Помилка при надсиланні правил:{Style.RESET_ALL} {e}")
        time.sleep(rules_interval)

def start_rules_thread(bot, chat_id):
    global rules_thread_started
    if not rules_thread_started:
        rules_thread_started = True
        rules_thread = threading.Thread(target=send_chat_rules, args=(bot, chat_id))
        rules_thread.daemon = True
        rules_thread.start()

def handle_new_user(bot, chat_id, new_user):
    chat_title = get_chat_title(bot, chat_id)
    username = new_user.get('username', '')
    first_name = new_user.get('first_name', '')
    full_name = f"{first_name} {username}".strip()

    # Перевірка через Perspective API
    api_url = f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={PERSPECTIVE_API_KEY}"
    payload = {
        "comment": {"text": full_name},
        "requestedAttributes": {"TOXICITY": {}, "SPAM": {}},
        "languages": ["en"],
    }

    try:
        response = requests.post(api_url, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            toxicity_score = result["attributeScores"]["TOXICITY"]["summaryScore"]["value"]
            spam_score = result["attributeScores"]["SPAM"]["summaryScore"]["value"]

            print(
                f"{Fore.CYAN}Перевірка імені нового користувача:{Style.RESET_ALL} '{full_name}' | TOXICITY={toxicity_score:.2f} | SPAM={spam_score:.2f}")

            if toxicity_score > 0.65 or spam_score > 0.75:
                bot.kickChatMember(chat_id, new_user['id'])
                bot.sendMessage(chat_id,
                                f"🚫 Користувач [{full_name}](tg://user?id={new_user['id']}) був забанений через підозріле ім'я!",
                                parse_mode='Markdown')
                logging.info(
                    "New user banned: Suspicious username",
                    extra={
                        'chat_id': chat_id,
                        'chat_title': chat_title,
                        'user_id': new_user['id'],
                        'username': full_name,
                        'details': f"TOXICITY={toxicity_score:.2f}, SPAM={spam_score:.2f}"
                    }
                )
                return
    except requests.RequestException as e:
        print(f"{Fore.RED}Помилка перевірки імені через API:{Style.RESET_ALL} {e}")

    # Існуюча перевірка на лайливі слова
    curse_words = load_curse_words("curse_words.json")
    if check_for_curse_words(full_name.lower(), curse_words):
        try:
            bot.kickChatMember(chat_id, new_user['id'])
            bot.sendMessage(chat_id,
                            f"🚫 Користувач [{full_name}](tg://user?id={new_user['id']}) був забанений за використання ненормативної лексики у нікнеймі!",
                            parse_mode='Markdown')
            logging.info(
                "New user banned: Curse word in username",
                extra={
                    'chat_id': chat_id,
                    'chat_title': chat_title,
                    'user_id': new_user['id'],
                    'username': full_name,
                    'details': "Banned"
                }
            )
        except Exception as e:
            print(f"{Fore.RED}Помилка при бані користувача:{Style.RESET_ALL} {full_name} з ID {new_user['id']} - {e}")
    else:
        bot.sendMessage(chat_id, f"👋 Ласкаво просимо, [{full_name}](tg://user?id={new_user['id']}), до '{chat_title}'!",
                        parse_mode='Markdown')
        bot.sendMessage(chat_id,
                        f"🛡️ [{full_name}](tg://user?id={new_user['id']}), ви можете зняти обмеження, написавши боту 'Я не бот' в особисті повідомлення протягом 5 хвилин, інакше вас буде забанено.",
                        parse_mode='Markdown')

        bot.restrictChatMember(
            chat_id, new_user['id'],
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        new_user_restrictions[new_user['id']] = {'chat_id': chat_id, 'time': time.time()}
        logging.info(
            "New user restricted",
            extra={
                'chat_id': chat_id,
                'chat_title': chat_title,
                'user_id': new_user['id'],
                'username': full_name,
                'details': "Restricted until verification"
            }
        )

def handle(bot, msg):
    chat_type = msg['chat']['type']
    if chat_type not in ['group', 'supergroup']:
        return

    chat_id = msg['chat']['id']
    user_id = msg['from']['id']

    start_rules_thread(bot, chat_id)

    if 'new_chat_members' in msg:
        for new_user in msg['new_chat_members']:
            handle_new_user(bot, chat_id, new_user)
        return

    if handle_spam(bot, msg, chat_id, user_id):
        return

    if handle_curse_words(bot, msg, chat_id, user_id):
        return

    if handle_suspicious_links(bot, msg, chat_id, user_id):
        return

    if handle_spam_text(bot, msg, chat_id, user_id):
        return

    text = msg.get('text', '').lower()
    if text.startswith('/ban'):
        handle_ban_command(bot, msg, chat_id, user_id)
    elif text.startswith('/mute'):
        handle_mute_command(bot, msg, chat_id, user_id)
    elif text.startswith('/unmute'):
        handle_unmute_command(bot, msg, chat_id, user_id)
    elif text.startswith('/add_curse_word'):
        handle_add_curse_word_command(bot, msg, chat_id, user_id)
    elif text.startswith('/report'):
        handle_report_command(bot, msg, chat_id, user_id)
    elif text.startswith('/appeal'):  # Додано обробку команди /appeal
        handle_appeal_command(bot, msg, chat_id, user_id)

def handle_private_message(bot, msg):
    user_id = msg['from']['id']
    text = msg.get('text', '').lower()

    if text == 'я не бот':
        bot.sendMessage(user_id, "✅ Ви успішно пройшли перевірку. Обмеження знято.")
        if user_id in new_user_restrictions:
            group_chat_id = new_user_restrictions[user_id]['chat_id']
            chat_title = get_chat_title(bot, group_chat_id)
            bot.restrictChatMember(
                group_chat_id, user_id,
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            logging.info(
                "User verified",
                extra={
                    'chat_id': group_chat_id,
                    'chat_title': chat_title,
                    'user_id': user_id,
                    'username': get_username(msg),
                    'details': "Restrictions lifted"
                }
            )
            del new_user_restrictions[user_id]
    elif text.startswith('/appeal'):  # Додано обробку /appeal у приватних повідомленнях
        handle_appeal_command(bot, msg, None, user_id)

def check_new_user_restrictions(bot):
    while True:
        current_time = time.time()
        for user_id, restriction in list(new_user_restrictions.items()):
            if current_time - restriction['time'] > 300:
                chat_id = restriction['chat_id']
                chat_title = get_chat_title(bot, chat_id)
                bot.kickChatMember(chat_id, user_id)
                bot.sendMessage(chat_id,
                                f"🚫 Користувач з ID [{user_id}](tg://user?id={user_id}) був забанений у '{chat_title}' за невиконання перевірки 'Я не бот'.",
                                parse_mode='Markdown')
                logging.info(
                    "New user banned: Verification timeout",
                    extra={
                        'chat_id': chat_id,
                        'chat_title': chat_title,
                        'user_id': user_id,
                        'username': 'Unknown',
                        'details': "Banned"
                    }
                )
                del new_user_restrictions[user_id]
        time.sleep(30)

def message_loop(msg):
    chat_type = msg['chat']['type']
    if chat_type == 'private':
        handle_private_message(bot, msg)
    else:
        handle(bot, msg)

def start_bot(bot_instance):
    global bot
    bot = bot_instance
    bot.message_loop(message_loop)
    restrictions_thread = threading.Thread(target=check_new_user_restrictions, args=(bot,))
    restrictions_thread.daemon = True
    restrictions_thread.start()