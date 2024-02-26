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
        users_collection.insert_one({'telegramId': message.from_user.id})

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    item1 = types.KeyboardButton("Наші проекти")
    markup.add(item1)

    bot.send_message(message.chat.id, "Головне меню:", reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def send_zk_list(message):
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


# Function to handle the feedback form
def handle_feedback(message):
    bot.send_message(message.chat.id, "Будь ласка, введіть ваше повідомлення")
    bot.register_next_step_handler(message, send_feedback)


def send_feedback(message):
    # Forward the message to all admin IDs
    for admin_id in ADMIN_IDS:
        bot.forward_message(admin_id, message.chat.id, message.message_id)
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
    feedback_button = types.InlineKeyboardButton(text="Зворотній зв'язок", callback_data="feedback")
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
    elif call.data == "feedback":
        handle_feedback(call.message)
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
