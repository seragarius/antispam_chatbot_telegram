import telepot
from utils import get_violations, update_violations, reset_violations, decrement_violations, get_username, \
    add_curse_word, load_curse_words, can_report, logging, user_last_reports, muted_users, get_chat_title
from checks import is_admin, timeout_stages, is_user_muted
import time


def handle_ban_command(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    if is_admin(bot, chat_id, user_id):
        if 'reply_to_message' in msg:
            reply_message = msg['reply_to_message']
            user_to_ban_id = reply_message['from']['id']

            if user_to_ban_id == bot.getMe()['id']:
                bot.sendMessage(chat_id, "❌ Ви не можете забанити бота!", reply_to_message_id=msg['message_id'])
                return
            if is_admin(bot, chat_id, user_to_ban_id):
                bot.sendMessage(chat_id, "❌ Ви не можете забанити адміністратора!",
                                reply_to_message_id=msg['message_id'])
                return

            user_to_ban_username = get_username(reply_message)
            try:
                bot.kickChatMember(chat_id, user_to_ban_id)
                bot.sendMessage(chat_id, f"🚫 [{user_to_ban_username}](tg://user?id={user_to_ban_id}) був забанений!",
                                parse_mode='Markdown')
                reset_violations(user_to_ban_id)
                if user_to_ban_id in muted_users:
                    del muted_users[user_to_ban_id]  # Видаляємо з muted_users при банні
                logging.info(
                    "Ban: User banned",
                    extra={
                        'chat_id': chat_id,
                        'chat_title': chat_title,
                        'user_id': user_to_ban_id,
                        'username': user_to_ban_username,
                        'details': f"Message: {reply_message.get('text', 'N/A')}"
                    }
                )
            except Exception as e:
                print(f"Error banning user: {e}")
                bot.sendMessage(chat_id, "У мене немає прав на бан цього користувача.",
                                reply_to_message_id=msg['message_id'])
        else:
            bot.sendMessage(chat_id, "Будь ласка, відповідайте на повідомлення користувача, щоб заблокувати його.",
                            reply_to_message_id=msg['message_id'])
    else:
        bot.deleteMessage((chat_id, msg['message_id']))


def handle_mute_command(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    if is_admin(bot, chat_id, user_id):
        if 'reply_to_message' in msg:
            reply_message = msg['reply_to_message']
            user_to_mute_id = reply_message['from']['id']

            if user_to_mute_id == bot.getMe()['id']:
                bot.sendMessage(chat_id, "❌ Ви не можете застосувати команду до бота!",
                                reply_to_message_id=msg['message_id'])
                return
            if is_admin(bot, chat_id, user_to_mute_id):
                bot.sendMessage(chat_id, "❌ Ви не можете застосувати команду до адміністратора!",
                                reply_to_message_id=msg['message_id'])
                return

            user_to_mute_username = get_username(reply_message)
            restrict_info = bot.getChatMember(chat_id, user_to_mute_id)

            if restrict_info['status'] in ['member', 'administrator', 'creator']:
                violations = get_violations(user_to_mute_id)
                update_violations(user_to_mute_id)
                timeout = timeout_stages[violations] if violations < len(timeout_stages) else timeout_stages[-1]

                bot.restrictChatMember(
                    chat_id, user_to_mute_id,
                    until_date=int(time.time()) + timeout,
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                )
                muted_users[user_to_mute_id] = {'chat_id': chat_id,
                                                'until_date': int(time.time()) + timeout}  # Додаємо до muted_users
                bot.sendMessage(chat_id,
                                f"🔇 [{user_to_mute_username}](tg://user?id={user_to_mute_id}) отримав таймаут на {timeout // 3600} годин!",
                                parse_mode='Markdown')
                logging.info(
                    "Mute: User muted",
                    extra={
                        'chat_id': chat_id,
                        'chat_title': chat_title,
                        'user_id': user_to_mute_id,
                        'username': user_to_mute_username,
                        'details': f"Message: {reply_message.get('text', 'N/A')} - Timeout: {timeout // 3600} hours"
                    }
                )
            else:
                bot.sendMessage(chat_id,
                                f"[{user_to_mute_username}](tg://user?id={user_to_mute_id}) вже має мут у групі'{chat_title}', неможливо застосувати команду.",
                                parse_mode='Markdown', reply_to_message_id=msg['message_id'])
        else:
            bot.sendMessage(chat_id,
                            "Будь ласка, відповідайте на повідомлення користувача, щоб поставити йому таймаут.",
                            reply_to_message_id=msg['message_id'])
    else:
        bot.deleteMessage((chat_id, msg['message_id']))


def handle_unmute_command(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    if is_admin(bot, chat_id, user_id):
        if 'reply_to_message' in msg:
            reply_message = msg['reply_to_message']
            user_to_unmute_id = reply_message['from']['id']

            if user_to_unmute_id == bot.getMe()['id']:
                bot.sendMessage(chat_id, "❌ Ви не можете зняти мут з бота!", reply_to_message_id=msg['message_id'])
                return
            if is_admin(bot, chat_id, user_to_unmute_id):
                bot.sendMessage(chat_id, "❌ Ви не можете зняти мут з адміністратора!",
                                reply_to_message_id=msg['message_id'])
                return

            user_to_unmute_username = get_username(reply_message)
            restrict_info = bot.getChatMember(chat_id, user_to_unmute_id)

            if restrict_info['status'] not in ['member', 'administrator', 'creator']:
                bot.restrictChatMember(
                    chat_id, user_to_unmute_id,
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
                if user_to_unmute_id in muted_users:
                    del muted_users[user_to_unmute_id]  # Видаляємо з muted_users при розмуті
                bot.sendMessage(chat_id,
                                f"✅ [{user_to_unmute_username}](tg://user?id={user_to_unmute_id}) більше не має обмежень!",
                                parse_mode='Markdown')
                violations = get_violations(user_to_unmute_id)
                if violations > 0:
                    decrement_violations(user_to_unmute_id)
                logging.info(
                    "Unmute: User unmuted",
                    extra={
                        'chat_id': chat_id,
                        'chat_title': chat_title,
                        'user_id': user_to_unmute_id,
                        'username': user_to_unmute_username,
                        'details': f"Message: {reply_message.get('text', 'N/A')}"
                    }
                )
            else:
                bot.sendMessage(chat_id, f"[{user_to_unmute_username}](tg://user?id={user_to_unmute_id}) не має мута у '{chat_title}'!",
                                parse_mode='Markdown', reply_to_message_id=msg['message_id'])
        else:
            bot.sendMessage(chat_id, "Будь ласка, відповідайте на повідомлення користувача, щоб зняти з нього мут.",
                            reply_to_message_id=msg['message_id'])
    else:
        bot.deleteMessage((chat_id, msg['message_id']))


def handle_add_curse_word_command(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    if is_admin(bot, chat_id, user_id):
        parts = msg.get('text', '').split(" ", 1)
        if len(parts) < 2:
            bot.sendMessage(chat_id, "Будь ласка, надайте слово для додавання.", reply_to_message_id=msg['message_id'])
            return

        word = parts[1].strip()
        curse_words = load_curse_words("curse_words.json")

        if word.lower() in curse_words:
            bot.sendMessage(chat_id, f"Слово '{word}' вже є в списку лайливих слів.",
                            reply_to_message_id=msg['message_id'])
            return

        result = add_curse_word(user_id, word)
        bot.sendMessage(chat_id, result, reply_to_message_id=msg['message_id'])
        logging.info(
            "Curse word added",
            extra={
                'chat_id': chat_id,
                'chat_title': chat_title,
                'user_id': user_id,
                'username': get_username(msg),
                'details': f"Word: {word}"
            }
        )
    else:
        bot.deleteMessage((chat_id, msg['message_id']))
        bot.sendMessage(chat_id, f"❌ Ви не є адміністратором чату '{chat_title}'.", reply_to_message_id=msg['message_id'])


def handle_report_command(bot, msg, chat_id, user_id):
    chat_title = get_chat_title(bot, chat_id)
    if 'reply_to_message' in msg:
        reply_message = msg['reply_to_message']
        reported_user_id = reply_message['from']['id']
        reported_username = get_username(reply_message)
        reported_message_id = reply_message['message_id']

        if can_report(user_id):
            admins = bot.getChatAdministrators(chat_id)
            for admin in admins:
                admin_id = admin['user']['id']
                if not bot.getChatMember(chat_id, admin_id)['user']['is_bot']:
                    bot.forwardMessage(admin_id, chat_id, reported_message_id)
            bot.sendMessage(chat_id,
                            f"✅ Репорт від [{get_username(msg)}](tg://user?id={user_id}) надіслано адміністраторам чату '{chat_title}'. Повідомлення від [{reported_username}](tg://user?id={reported_user_id}) розглядається.",
                            parse_mode='Markdown', reply_to_message_id=msg['message_id'])
            logging.info(
                "Report: Message reported",
                extra={
                    'chat_id': chat_id,
                    'chat_title': chat_title,
                    'user_id': user_id,
                    'username': get_username(msg),
                    'details': f"Reported user: {reported_user_id}, Message: {reply_message.get('text', 'N/A')}"
                }
            )
        else:
            bot.sendMessage(chat_id, "❌ Ви можете використовувати команду /report не частіше ніж раз на 2 хвилини.",
                            reply_to_message_id=msg['message_id'])
    else:
        bot.sendMessage(chat_id, "❌ Ви повинні відповісти на повідомлення, щоб повідомити про нього.",
                        reply_to_message_id=msg['message_id'])


def handle_appeal_command(bot, msg, chat_id, user_id):
    username = get_username(msg)
    is_muted = is_user_muted(bot, chat_id, user_id) if chat_id else False
    appeal_text = msg.get('text', '').replace('/appeal', '').strip()
    appeal_message = f"📝 Апеляція від [{username}](tg://user?id={user_id}): {appeal_text}"

    # Перевірка наявності тексту в апеляції
    if not appeal_text:
        bot.sendMessage(chat_id or user_id,
                        "❌ Будь ласка, додайте пояснення до вашої апеляції (наприклад, /appeal Я не порушував правила).",
                        parse_mode='Markdown', reply_to_message_id=msg['message_id'] if chat_id else None)
        return

    # Обмеження на частоту звернень (раз на 10 хвилин)
    current_time = time.time()
    if user_id in user_last_reports and (current_time - user_last_reports[user_id] < 600):
        bot.sendMessage(chat_id or user_id, "❌ Ви можете подавати апеляцію не частіше ніж раз на 10 хвилин.",
                        parse_mode='Markdown', reply_to_message_id=msg['message_id'] if chat_id else None)
        return

    if chat_id:  # Якщо команда з групи
        chat_title = get_chat_title(bot, chat_id)
        if not is_muted:
            bot.sendMessage(chat_id,
                            f"❌ [{username}](tg://user?id={user_id}), у вас немає активного мута в чаті '{chat_title}' для оскарження.",
                            parse_mode='Markdown', reply_to_message_id=msg['message_id'])
            return

        # Надсилаємо апеляцію адміністраторам
        admins = bot.getChatAdministrators(chat_id)
        for admin in admins:
            admin_id = admin['user']['id']
            if not bot.getChatMember(chat_id, admin_id)['user']['is_bot']:
                try:
                    bot.sendMessage(admin_id, f"{appeal_message} (Чат: {chat_title})", parse_mode='Markdown')
                except Exception as e:
                    print(f"Помилка надсилання апеляції адміністратору {admin_id}: {e}")
        bot.sendMessage(chat_id, f"✅ [{username}](tg://user?id={user_id}), ваше звернення надіслано адміністраторам чату '{chat_title}'.",
                        parse_mode='Markdown', reply_to_message_id=msg['message_id'])

        # Оновлюємо час лише після успішної відправки
        user_last_reports[user_id] = current_time

        logging.info(
            "Appeal: Appeal submitted from group",
            extra={
                'chat_id': chat_id,
                'chat_title': chat_title,
                'user_id': user_id,
                'username': username,
                'details': f"Appeal text: {appeal_text}"
            }
        )
    else:  # Якщо команда з приватного чату
        muted_chat_id = muted_users.get(user_id, {}).get('chat_id')
        if muted_chat_id and is_user_muted(bot, muted_chat_id, user_id):
            chat_title = get_chat_title(bot, muted_chat_id)
            admins = bot.getChatAdministrators(muted_chat_id)
            for admin in admins:
                admin_id = admin['user']['id']
                if not bot.getChatMember(muted_chat_id, admin_id)['user']['is_bot']:
                    try:
                        bot.sendMessage(admin_id, f"{appeal_message} (Чат: {chat_title})", parse_mode='Markdown')
                    except Exception as e:
                        print(f"Помилка надсилання апеляції адміністратору {admin_id}: {e}")
            bot.sendMessage(user_id, f"✅ Ваше звернення надіслано адміністраторам чату '{chat_title}'.")

            # Оновлюємо час лише після успішної відправки
            user_last_reports[user_id] = current_time
        else:
            bot.sendMessage(user_id,
                            "❌ Не вдалося знайти чат, де ви маєте мут. Уточніть адміністраторам вручну або спробуйте з групи.")
            return

        logging.info(
            "Appeal: Appeal submitted from private",
            extra={
                'chat_id': muted_chat_id or 'Unknown',
                'chat_title': chat_title if muted_chat_id else 'Unknown',
                'user_id': user_id,
                'username': username,
                'details': f"Appeal text: {appeal_text}"
            }
        )