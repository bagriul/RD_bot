import telebot
from telebot import types
import requests
import config
import pymongo

bot = telebot.TeleBot(config.BOT_TOKEN)

ADMIN_IDS = config.ADMIN_IDS

client = pymongo.MongoClient(config.MONGO_STRING)
db = client['ResidentDevelopment']
users_collection = db['users']

message_template = '''
*{title}*
{location}

{status}
*Кількість будинків* - {buildings}.
*Поверховість* - {floors}.
*Кількість квартир* - {rooms}.

{details}

*Інфраструктура*
{infrastructure}

*{price}*

{sales_department}
'''


@bot.message_handler(commands=['start'])
def start(message):
    is_present = users_collection.find_one({'telegramId': message.from_user.id})
    if is_present is None:
        users_collection.insert_one({'telegramId': message.from_user.id,
                                     'firstName': message.from_user.first_name,
                                     'lastName': message.from_user.last_name})

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    item1 = types.KeyboardButton("Наші проекти")
    item2 = types.KeyboardButton("Про нас")
    item3 = types.KeyboardButton("Відділи продажів")
    markup.add(item1, item2, item3)

    bot.send_photo(message.chat.id, photo='https://img.lunstatic.net/company-600x300/1872.jpg', caption=config.about_text)
    bot.send_message(message.chat.id, "Головне меню:", reply_markup=markup)


@bot.message_handler(commands=['about'])
def about(message):
    bot.send_photo(message.chat.id, photo='https://img.lunstatic.net/company-600x300/1872.jpg',
                   caption=config.about_text)


@bot.message_handler(commands=['sales'])
def sales(message):
    bot.send_message(message.from_user.id, 'Центральний відділ продажу\n'
                                           'Resident Development:\n'
                                           '[вул. Садова 2е](https://maps.app.goo.gl/N7S2nhWwHMDActqs6)\n'
                                           'Пн. - Пт. - 09:00 - 18:00\n'
                                           'Неділя - Вихідний\n'
                                           '[+38 (073) 321 34 49](tel://+380733213449)\n\n'
                                           'ЖК N69 Residents:\n'
                                           '[вул. Навроцького 69, А-2](https://maps.app.goo.gl/jgW1r88UnjDBnoTB8)\n'
                                           'Пн. - Пт. - 09:00 - 18:00\n'
                                           'Неділя - Вихідний\n'
                                           '[+38 (073) 464 77 89](tel://+380734647789)', parse_mode='Markdown', disable_web_page_preview=True)


@bot.message_handler(func=lambda message: True)
def send_zk_list(message):
    if message.text == 'Наші проекти':
        response = requests.get('https://api.resident-development.com/api/projects/')
        data = response.json()["data"]["projects"]
        keyboard = types.InlineKeyboardMarkup()
        for project in data:
            title = project['title']
            if 'NOVO Residence' in title:
                title = 'NOVO Residence'
            button = types.InlineKeyboardButton(text=title, callback_data=f"zk_{project['alias']}")
            keyboard.add(button)
        bot.send_message(message.from_user.id, text="Наші проекти:", reply_markup=keyboard)
    if message.text == 'Про нас':
        about(message)
    if message.text == 'Відділи продажів':
        sales(message)


def handle_feedback(callback_query):
    zk = callback_query.data.split('_')[1]
    bot.send_message(callback_query.from_user.id, "Будь ласка, введіть ваше ім'я")
    bot.register_next_step_handler(callback_query.message, receive_name, zk)

def receive_name(message, zk):
    name = message.text
    # Save or process the name as needed
    # For example: save it in a variable or database
    bot.send_message(message.chat.id, "Тепер введіть ваш номер телефону")
    bot.register_next_step_handler(message, receive_phone, name, zk)

def receive_phone(message, name, zk):
    phone_number = message.text
    # Save or process the phone number as needed
    # For example: save it in a variable or database
    bot.send_message(message.chat.id, "Тепер введіть ваше повідомлення")
    bot.register_next_step_handler(message, send_feedback, name, phone_number, zk)

def send_feedback(message, name, phone_number, zk):
    # Forward the message along with name and phone number to all admin IDs
    feedback_info = (f"Ім'я: {name}\nНомер телефону: {phone_number}\nПовідомлення: {message.text}\n"
                     f"Об'єкт: {zk}")
    for admin_id in ADMIN_IDS:
        bot.send_message(admin_id, feedback_info)
    bot.send_message(message.chat.id, "Ваше повідомлення надіслано адміністратору")



def send_info(zk, userId):
    page = requests.get(f'https://api.resident-development.com/api/projects/{zk}')
    data_json = page.json()['data']
    if 'NOVO Residence' in data_json["project"]["title"]:
        title = f'ЖК {data_json["project"]["title"]}'
    else:
        title = f'ЖК "{data_json["project"]["title"]}"'
    location = data_json["project"]['region']
    status = f'Готовність: {data_json["project"]["status"]}'
    buildings = data_json["project"]["fields"]['number_of_houses']
    floors = data_json["project"]["fields"]['number_of_floors']
    rooms = data_json["project"]["fields"]['number_of_rooms']
    try:
        floors = floors.replace('<br/>', '')
    except AttributeError:
        pass
    price = f'Початкова ціна за м2 = {data_json["project"]["price"]}$'
    try:
        sales_department = f'*Відділ продажу:* {data_json["project"]["sales_department"]}'
    except KeyError:
        sales_department = '*Відділ продажу:*'
    try:
        phone = data_json['project']['phone_number'].replace(' ', '')
    except KeyError:
        phone = '+380672124130'
    try:
        details = config.zk_info[zk]['details']
        infrastructure = config.zk_info[zk]['infrastructure']
    except KeyError:
        details = ''
        infrastructure = ''
    medias = data_json['project']['media']
    photos = []
    for media in medias:
        if media['collection_name'] == 'project-gallery':
            allowed_formats = ['.jpg', '.jpeg', '.png']
            if any(format in media['url'] for format in allowed_formats):
                pass
            else:
                continue
            photos.append(media['url'])
    data = {'title': title,
            'location': location,
            'status': status,
            'buildings': buildings,
            'floors': floors,
            'rooms': rooms,
            'price': price,
            'sales_department': sales_department,
            'details': details,
            'infrastructure': infrastructure,
            'website': f'https://resident-development.com/projects/{zk}/about'}

    msg = message_template.format(**data)
    keyboard = types.InlineKeyboardMarkup()
    website_button = types.InlineKeyboardButton(text="Вебсайт", url=data['website'])
    feedback_button = types.InlineKeyboardButton(text="Зворотній зв'язок", callback_data=f"feedback_{title}")
    phone_button = types.InlineKeyboardButton(text="Зателефонувати", callback_data=f"phone_{phone}")
    keyboard.add(website_button, feedback_button, phone_button)
    media_group = []
    for photo in photos:
        media_group.append(types.InputMediaPhoto(media=photo))
    bot.send_media_group(userId, media_group)
    bot.send_message(userId, text=msg, reply_markup=keyboard, parse_mode='Markdown')


# Handler for inline buttons
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data.startswith("zk"):
        send_info(call.data[3:], call.from_user.id)
    elif call.data.startswith("feedback"):
        handle_feedback(call)
    elif call.data.startswith('phone'):
        phone = call.data.split('_')
        bot.send_contact(call.message.chat.id, phone_number=phone[1], first_name="Відділ Продажу")


@bot.message_handler(commands=['send'])
def send_to_all(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "У вас немає доступу")
        return

    bot.reply_to(message, "Введіть повідомлення")
    bot.register_next_step_handler(message, handle_message_input)


def handle_message_input(message):
    admin_id = message.from_user.id
    message_text = message.text

    # Check if the message contains a photo
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        users = users_collection.find()
        for user in users:
            user_id = user.get("telegramId")
            bot.send_photo(user_id, photo_file_id, caption=message.caption)
    else:
        users = users_collection.find()
        for user in users:
            user_id = user.get("telegramId")
            bot.send_message(user_id, message_text)

    bot.reply_to(message, "Повідомлення успішно надіслано")


bot.polling(none_stop=True)
