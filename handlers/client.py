from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from data_base import mysql_db
from create_bot import bot
from keyboards import client_kb
from collections import deque
import json
import datetime
from config.config import conf


# /start, /help - handler. Start message
async def start_handler(message: types.Message):
    await message.answer("Привет, вот пояснение к предоставленным ниже кнопкам:\n\n"
                         "🚎/🚌 - можно посмотреть через какие остановки едет транспортное средство.\n\n"
                         "🕐 - расписание заданной остановки.\n\n"
                         "🔎🚍 - помогу тебе доехать из точки А в точку Б.\n\n"
                         "🗺 - если ты турист или потерялся, я помогу найти ближайшую остановку =).\n\n"
                         "💰 - актуальные цены на проезд и проездные билеты.\n\n"
                         "💬 - тут вы можете оставить свой комментарий о работе бота или указать на неточность\n\n",
                         reply_markup=client_kb.get_main_kb())


# definition StatesGroup
class TransRouteState(StatesGroup):
    waiting_for_trans_type = State()
    waiting_for_trans_num = State()
    waiting_for_trans_route_id = State()


# 🚎/🚌 command handler
async def trans_route_handler(message: types.Message):
    # send a message with an explanation to the keyboard
    await message.answer("🚎 - троллейбусы\n"
                         "🚌 - автобусы\n"
                         "Отмена - вернуться назад",
                         reply_markup=client_kb.get_trans_choice_kb())
    await TransRouteState.waiting_for_trans_type.set()


# TransRouteState.waiting_for_trans_type
async def process_transport_type(message: types.Message, state: FSMContext):
    # checking message for entry in 🚎 or 🚌
    if message.content_type == types.ContentType.TEXT and message.text in ["🚎", "🚌"]:
        await message.answer("Отправьте номер транспорта, если имеется буква в номере пишите ее на крилице слитно..\n"
                             "Пример: 11б, 2а", reply_markup=client_kb.get_cancel_kb())
        trans_type = True
        if message.text == "🚎":
            trans_type = False
        async with state.proxy() as data:
            data['trans_type'] = trans_type
        await TransRouteState.waiting_for_trans_num.set()
    else:
        await message.answer('Ой ой ой, воспользуйтесь кнопками 🚎, 🚌 или "Отмена"')


# cancellation handler | ONLY FOR STATE HANDLERS
async def proccess_cancel(message: types.Message, state: FSMContext):
    await message.answer("Вы были возвращены в главное меню!", reply_markup=client_kb.get_main_kb())
    await state.finish()


# Handler for the State TransRouteState.waiting_for_trans_num state
async def proccess_trans_num(message: types.Message, state: FSMContext):
    if message.content_type == types.ContentType.TEXT:
        async with state.proxy() as data:
            # Extracting the value of trans_type from the user's session
            # The initialization took place in the process_transport_type function
            trans_type = data['trans_type']
        trans_names = await mysql_db.get_trans_name_by_num(mysql_db.pool, message.text, trans_type)
        # Checking if there were any transport names found
        if trans_names:
            # Creating an inline keyboard
            markup = types.InlineKeyboardMarkup()
            for trans in trans_names:
                button = types.InlineKeyboardButton(trans['trans_name'], callback_data=f"trans_id_{trans['trans_id']}")
                markup.add(button)

            await message.answer("Выбирите направление маршрута:", reply_markup=markup)
            await TransRouteState.waiting_for_trans_route_id.set()
        else:  # If no transport was found
            if trans_type:
                trans_type = "Автобуса"
            else:
                trans_type = "Троллейбуса"
            await message.answer(f"{trans_type} с таким номером не нашлось, возможно вы где-то ошиблись."
                                 f" Попробуйте еще раз!")
    else:  # If the incoming message is not text
        await message.answer("Не верный тип сообщения, отправьте текст.")


# Handler for processing a callback for the State TransRouteState.waiting_for_trans_route_id
async def process_transport_route_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Extract the transport id from the callback data
    trans_id = callback_query.data.replace("trans_id_", "")

    route_name = await mysql_db.get_trans_by_id(mysql_db.pool, int(trans_id))
    route_stops = await mysql_db.get_route_by_trans_id(mysql_db.pool, int(trans_id))

    # Construct the response message
    response = f"Остановки маршрута {route_name['trans_name']}:"

    # Delete the original message from the bot to keep the chat clean
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

    # Create an inline keyboard for the stops on the route
    markup = types.InlineKeyboardMarkup()
    for route in route_stops:
        button = types.InlineKeyboardButton(route['stop_name'], callback_data=f"route_id_{route['route_id']}")
        markup.add(button)

    await bot.send_message(callback_query.from_user.id, response, reply_markup=markup)
    await bot.send_message(callback_query.from_user.id, "При нажатии на кнопки выше, можно посмотреть расписание для "
                                                        "данного транспорта на конкретной остановке",
                           reply_markup=client_kb.get_main_kb())
    await state.finish()


# Asynchronous function to process a callback with route stop information
async def process_timeboard_for_route_stop(callback_query: types.CallbackQuery):
    # Extract the route id from the callback data
    route_id = callback_query.data.replace("route_id_", "")

    trans_num, trans_name, trans_type, stop_name, timeboard_new = \
        await mysql_db.get_schedule_by_route_id(mysql_db.pool, int(route_id))
    timeboard_new = json.loads(timeboard_new)

    # Delete the original message from the bot to keep the chat clean
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

    # Nested function to format the timeboard
    def format_timeboard(timeboard):
        hours = {}
        for time in timeboard:
            hour, minute = time.split(':')
            if hour not in hours:
                hours[hour] = []
            hours[hour].append(minute)

        formatted_timeboard = ''
        for hour, minutes in hours.items():
            formatted_timeboard += f'{hour}: {"| ".join(minutes)}\n'
        return formatted_timeboard

    # Determine the type of transport based on the value of trans_type
    if trans_type:
        trans_type = "автобуса"
    else:
        trans_type = "троллейбуса"

    # Begin constructing the response message
    response = f"Расписание для {trans_type} №{trans_num}\n{trans_name}\n" \
               f"На остановке {stop_name}\n"

    # Add each day's schedule to the response message
    for day, times in timeboard_new.items():
        response += f"{day}\n{format_timeboard(times)}\n"

    await callback_query.message.answer(response)


# определение StatesGroup
class StopState(StatesGroup):
    waiting_for_stop = State()


# обработчик команды 🕐
async def stop_timeboard_handler(message: types.Message):
    await message.answer("Отправьте название остановки либо ее геолокацию!",
                         reply_markup=client_kb.get_cancel_kb())
    await StopState.waiting_for_stop.set()


# обработчик остановки
async def process_stop(message: types.Message):
    sought_stops = None
    # Проверяем тип сообщения
    if message.content_type == types.ContentType.TEXT:
        stops = await mysql_db.get_stops_levenshtein_distance(mysql_db.pool, message.text)
        if not stops:
            await message.answer('Попробуйте ввести название более точно')
        else:
            min_distance = min(stops, key=lambda x: x['distance'])['distance']
            if min_distance == 0:
                sought_stops = [stop for stop in stops if stop['distance'] == 0]
            else:
                sought_stops = stops
    elif message.content_type == types.ContentType.LOCATION:
        stops = await mysql_db.get_stops_by_location(mysql_db.pool, message.location.latitude, message.location.longitude)
        if not stops:
            await message.answer('В радиусе 100 метров от точки нету остановок, попробуйте поставить точку геолокации '
                                 'более точно или напишите название остановки текстом')
        else:
            sought_stops = stops
    else:
        await message.answer(
            'Это что-то не то... Отправьте текстовое сообщение с названием остановки, либо ее геолокацию')
    if sought_stops:
        markup = types.InlineKeyboardMarkup()
        for stop in sought_stops:
            button = types.InlineKeyboardButton(stop['stop_name'] + " " + stop['add_info'],
                                                callback_data=f"stop_id_{stop['stop_id']}")
            markup.add(button)
        await message.answer("Возможно вы имели ввиду следующее, если ниже нет ващей остановки, "
                             "то попробуйте ввести заного.", reply_markup=markup)


async def process_stop_id_callback(callback_query: types.CallbackQuery, state: FSMContext):
    stop_id = callback_query.data.replace("stop_id_", "")
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

    timeboards = await mysql_db.get_schedule_by_stop_id(mysql_db.pool, int(stop_id))

    now = datetime.datetime.now()
    weekday = now.weekday()  # 0 - Monday, 1 - Tuesday, ..., 5 - Saturday, 6 - Sunday

    schedule_str = f"Расписание остановки {timeboards[0]['stop_name']}\n{timeboards[0]['add_info']}\n"
    for trans in timeboards:
        trans_type = "Автобус" if trans['trans_type'] else "Троллейбус"
        schedule_str += f"{trans_type} №{trans['trans_num']}:\n"

        # Select weekday, weekend or specific day schedule depending on current day
        time_board_new = json.loads(trans['time_board'])

        if weekday < 5:  # Monday to Friday
            time_board = time_board_new.get('Будни', [])
            no_service_message = "Маршрут не работает в Будни"
        elif weekday == 5:  # Saturday
            time_board = time_board_new.get('Суббота', time_board_new.get('Выходные', []))
            no_service_message = "Маршрут не работает в Выходные"
        elif weekday == 6:  # Sunday
            time_board = time_board_new.get('Воскресенье', time_board_new.get('Выходные', []))
            no_service_message = "Маршрут не работает в Выходные"

        if not time_board:
            schedule_str += f"{no_service_message}\n"
            continue

        time_list = [datetime.datetime.strptime(time_str, '%H:%M').time() for time_str in time_board]
        next_hour_time_list = [t for t in time_list if t > now.time() and t <= (
                datetime.datetime.combine(datetime.date.today(), now.time()) + datetime.timedelta(hours=1)).time()]

        if not next_hour_time_list:
            next_hour_time_list.extend([t for t in time_list if t > now.time()][:3])

        if next_hour_time_list:
            for time_item in next_hour_time_list:
                schedule_str += f"{time_item.strftime('%H:%M')}, "
            schedule_str = schedule_str.rstrip(", ") + "\n"
        else:
            schedule_str += "Маршрут окончил движение!\n"
    await callback_query.message.answer(schedule_str, reply_markup=client_kb.get_main_kb())
    await state.finish()


# определение StatesGroup
class RouteState(StatesGroup):
    waiting_for_first_location = State()
    waiting_for_second_location = State()


# обработчик команды 🔎🚍
async def cmd_distance(message: types.Message):
    # отправляем сообщение с просьбой прислать первую геолокацию
    await message.answer("Пожалуйста, отправьте геолокацию или название первой остановки.",
                         reply_markup=client_kb.get_cancel_kb())
    # переводим бота в состояние ожидания первой геолокации
    await RouteState.waiting_for_first_location.set()


async def find_stop_by_name(message, callback_tag):
    stop = None
    """func takes two argument:
        message: aiogram.types.Message
        callback_tag: str - tag
    """
    rows = await mysql_db.get_stops_levenshtein_distance(mysql_db.pool, message.text)
    if not rows:
        await message.answer('Попробуйте ввести название более точно')
    else:
        min_distance_row = min(rows, key=lambda x: x['distance'])
        stops_set = {row['stop_name'] for row in rows}
        # если остановку ввели корректно, либо если автокомплит показал только 1 остановку
        if min_distance_row['distance'] == 0 or len(stops_set) == 1:
            stop = min_distance_row['stop_name']
        # если в автокомплите более 1й остановки
        else:
            keyboard = []
            for stp in stops_set:
                button = types.InlineKeyboardButton(stp, callback_data=f'{callback_tag}{stp}')
                keyboard.append(button)
            markup = types.InlineKeyboardMarkup().row(*keyboard)
            await message.answer("Возможно вы имели ввиду следующее, если ниже нет ващей остановки, "
                                 "то попробуйте ввести заного.", reply_markup=markup)
    return stop


async def find_stop_by_location(message, callback_tag):
    stop = None
    """func takes two argument:
        message: aiogram.types.Message
        callback_tag: str - tag
    """
    rows = await mysql_db.get_stops_by_location(mysql_db.pool, message.location.latitude, message.location.longitude)
    if not rows:
        await message.answer(
            'В радиусе 100 метров от точки нету остановок, попробуйте поставить точку геолокации более '
            'точно или напишите название остановки текстом')
    else:
        stops_set = {row[0] for row in rows}
        if len(stops_set) == 1:
            stop = rows[0][0]
        # если в автокомплите более 1й остановки
        else:
            keyboard = []
            for stp in stops_set:
                button = types.InlineKeyboardButton(stp, callback_data=f'{callback_tag}{stp}')
                keyboard.append(button)
            markup = types.InlineKeyboardMarkup().row(*keyboard)
            await message.answer("Возможно вы имели ввиду следующее, если ниже нет ващей остановки, "
                                 "то попробуйте ввести заного.", reply_markup=markup)
    return stop


# обработчик первой геолокации
async def process_first_stop(message: types.Message, state: FSMContext):
    stop = None
    # Проверяем тип сообщения
    if message.content_type == types.ContentType.TEXT:
        stop = await find_stop_by_name(message, "firstStop_")
    elif message.content_type == types.ContentType.LOCATION:
        stop = await find_stop_by_location(message, "firstStop_")
    else:
        await message.answer(
            'Это что-то не то... Отправьте текстовое сообщение с названием остановки, либо ее геолокацию')
    # проверяем смогли ли мы найти остановку
    if stop is not None:
        async with state.proxy() as data:
            data['first_stop'] = stop
        # отправляем сообщение с просьбой прислать вторую геолокацию
        await message.answer("Отлично! Теперь отправьте вторую остановку.")
        # переводим бота в состояние ожидания второй геолокации
        await RouteState.waiting_for_second_location.set()


async def process_first_stop_callback(callback_query: types.CallbackQuery, state: FSMContext):
    stop_name = callback_query.data.replace("firstStop_", "")
    async with state.proxy() as data:
        data['first_stop'] = stop_name
    # удаляем инлайн клавиатуру отправляем сообщение с просьбой прислать вторую геолокацию
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id, "Отлично! Теперь отправьте вторую остановку.")
    # переводим бота в состояние ожидания второй геолокации
    await RouteState.waiting_for_second_location.set()


def bfs_paths(graph, start, goal):
    visited = {start}
    queue = deque([(start, [])])

    while queue:
        node, path = queue.popleft()
        for trans_id, stops in graph.items():
            if node in stops:
                for neighbor in stops:
                    if neighbor not in visited:
                        new_path = path + [(trans_id, node)]
                        if neighbor == goal:
                            yield new_path + [(trans_id, neighbor)]
                        else:
                            visited.add(neighbor)
                            queue.append((neighbor, new_path))


async def find_route_with_transfers(start_stop, end_stop):
    stops = await mysql_db.get_stops_by_names(mysql_db.pool,  start_stop, end_stop)
    routs = await mysql_db.get_all_routs(mysql_db.pool)
    graph = {}
    for route in routs:
        if route["trans_id"] not in graph:
            graph[route["trans_id"]] = set()
        graph[route["trans_id"]].add(route["cur_stop_id"])

    start_ids = [stop["stop_id"] for stop in stops if stop["stop_name"] == start_stop]
    end_ids = [stop["stop_id"] for stop in stops if stop["stop_name"] == end_stop]

    shortest_path = None
    min_transfers = float("inf")

    for start_id in start_ids:
        for end_id in end_ids:
            paths = bfs_paths(graph, start_id, end_id)
            for path in paths:
                transfers = len(set(transfer for transfer, _ in path)) - 1
                if transfers < min_transfers:
                    min_transfers = transfers
                    shortest_path = path

    if shortest_path is None:
        return "No routes found between the given stops."

    # Get transport and stop details for the shortest_path
    transport_stop_details = []
    for trans_id, stop_id in shortest_path:
        transport_details = await mysql_db.get_trans_by_id(mysql_db.pool, trans_id)
        stop_details = await mysql_db.get_stop_by_id(mysql_db.pool, stop_id)
        transport_stop_details.append((transport_details, stop_details))

    # Format the output
    output = []
    for i, (transport, stop) in enumerate(transport_stop_details):
        trans_type = "автобус" if transport["trans_type"] else "троллейбус"

        if i == 0:
            output.append(f"Садимся на {trans_type} №{transport['trans_num']} на остановке {stop['stop_name']}")
        elif transport_stop_details[i - 1][0]["trans_id"] != transport["trans_id"]:
            output.append(f"Пересадка на {trans_type} №{transport['trans_num']} на остановке {stop['stop_name']}")
        else:
            continue

    output.append(f"Выходим на остановке {transport_stop_details[-1][1]['stop_name']}")

    return "\n".join(output)


# обработчик второй геолокации
async def process_second_stop(message: types.Message, state: FSMContext):
    stop = None
    # Проверяем тип сообщения
    if message.content_type == types.ContentType.TEXT:
        stop = await find_stop_by_name(message, "secondStop_")
    elif message.content_type == types.ContentType.LOCATION:
        stop = await find_stop_by_location(message, "secondStop_")
    else:
        await message.answer(
            'Это что-то не то... Отправьте текстовое сообщение с названием остановки, либо ее геолокацию')
    # проверяем смогли ли мы найти остановку
    if stop is not None:
        async with state.proxy() as data:
            first_stop = data['first_stop']
        second_stop = stop
        s = await find_route_with_transfers(first_stop, second_stop)
        await message.answer(s, reply_markup=client_kb.get_main_kb())
        await state.finish()


async def process_second_stop_callback(callback_query: types.CallbackQuery, state: FSMContext):
    stop_name = callback_query.data.replace("secondStop_", "")
    async with state.proxy() as data:
        first_stop = data['first_stop']
    second_stop = stop_name
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    s = await find_route_with_transfers(first_stop, second_stop)
    await bot.send_message(callback_query.from_user.id, s, reply_markup=client_kb.get_main_kb())
    await state.finish()


# определение StatesGroup
class NearStopState(StatesGroup):
    waiting_for_location = State()


# обработка кнопки 🗺 (найти ближайшую остановку)
async def nearest_stop_handler(message: types.Message):
    await message.answer("Отправьте вашеместо положение и в ответ получите ближайшую остановку.",
                         reply_markup=client_kb.get_nearest_stop_kb())
    # переводим бота в состояние ожидания геолокации
    await NearStopState.waiting_for_location.set()


async def process_location(message: types.Message, state: FSMContext):
    if message.content_type == types.ContentType.LOCATION:
        closest_stop = await mysql_db.get_nearest_stop(mysql_db.pool, message.location.latitude, message.location.longitude)
        await message.answer(f"Ближайшая остановка {closest_stop['stop_name']}", reply_markup=client_kb.get_main_kb())
        await bot.send_location(chat_id=message.chat.id, latitude=closest_stop['latitude'],
                                longitude=closest_stop['longitude'])
        await state.finish()
    else:
        await message.answer('Это что-то не то... Нужно отправить геолокацию!')


def format_prices(prices):
    formatted_prices = {}
    for price in prices:
        ticket_type = price['type']
        location = price['location']
        price_value = price['price']

        if ticket_type not in formatted_prices:
            formatted_prices[ticket_type] = []
        formatted_prices[ticket_type].append((location, price_value))

    output = ""
    for ticket_type, info_list in formatted_prices.items():
        if len(info_list) > 1:
            output += f"{ticket_type}:\n"
            for i, (location, price_value) in enumerate(info_list, 1):
                output += f"    {i}) {location} - {price_value:.2f}\n"
        else:
            location, price_value = info_list[0]
            output += f"{ticket_type} - {location} - {price_value:.2f}"
        output += "\n"
    return output.strip()


# обработка кнопки 💰 (узнать текущие цены на проезд)
async def price_handler(message: types.Message):
    prices = await mysql_db.get_prices(mysql_db.pool)
    await message.answer(format_prices(prices))


# определение StatesGroup
class CommentState(StatesGroup):
    waiting_for_comment = State()


# обработка кнопки 💬 (оставить комментарий)
async def comment_handler(message: types.Message):
    await message.answer("Отправьте тексовый комментарий о работе бота.",
                         reply_markup=client_kb.get_cancel_kb())
    # переводим бота в состояние ожидания комментария
    await CommentState.waiting_for_comment.set()


async def leave_comment_process(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение с вашим комментарием.")

    await state.finish()

    # Сохраняем комментарий в базе данных
    mysql_db.save_comment(mysql_db.pool, message.from_user.id, message.text)

    await message.answer("Спасибо за ваш комментарий! Он был сохранен.", reply_markup=client_kb.get_main_kb())

    # Опционально: отправить уведомление админу о новом комментарии
    await bot.send_message(conf.get('bot', 'admin_id'), f"Новый комментарий от пользователя "
                                                        f"(ID: {message.from_user.id}):\n\n{message.text}")


def register_handlers_client(dp: Dispatcher):
    # start handler
    dp.register_message_handler(start_handler, commands=['start', 'help'])
    # unique cancel handler
    dp.register_message_handler(proccess_cancel, text="Отмена", state=[TransRouteState.waiting_for_trans_type,
                                                                       TransRouteState.waiting_for_trans_num,
                                                                       TransRouteState.waiting_for_trans_route_id,
                                                                       StopState.waiting_for_stop,
                                                                       RouteState.waiting_for_first_location,
                                                                       RouteState.waiting_for_second_location,
                                                                       NearStopState.waiting_for_location,
                                                                       CommentState.waiting_for_comment])

    # show trans route
    dp.register_message_handler(trans_route_handler, text="🚎/🚌")
    # 🚎/🚌 - handlers
    dp.register_message_handler(process_transport_type, content_types=types.ContentType.ANY,
                                state=TransRouteState.waiting_for_trans_type)
    dp.register_message_handler(proccess_trans_num, content_types=types.ContentType.ANY,
                                state=TransRouteState.waiting_for_trans_num)
    dp.register_callback_query_handler(process_transport_route_callback,
                                       lambda callback_query: callback_query.data.startswith('trans_id_'),
                                       state=TransRouteState.waiting_for_trans_route_id)
    dp.register_callback_query_handler(process_timeboard_for_route_stop,
                                       lambda callback_query: callback_query.data.startswith('route_id_'))

    # show stop schedule
    dp.register_message_handler(stop_timeboard_handler, text="🕐")
    # 🕐 - handlers
    dp.register_message_handler(process_stop, content_types=types.ContentType.ANY,
                                state=StopState.waiting_for_stop)
    dp.register_callback_query_handler(process_stop_id_callback,
                                       lambda callback_query: callback_query.data.startswith('stop_id_'),
                                       state=StopState.waiting_for_stop)

    # find route between stops
    dp.register_message_handler(cmd_distance, text="🔎🚍")
    # 🔎🚍 - handlers
    dp.register_message_handler(process_first_stop, content_types=types.ContentType.ANY,
                                state=RouteState.waiting_for_first_location)
    dp.register_callback_query_handler(process_first_stop_callback,
                                       lambda callback_query: callback_query.data.startswith('firstStop_'),
                                       state=RouteState.waiting_for_first_location)
    dp.register_message_handler(process_second_stop, content_types=types.ContentType.ANY,
                                state=RouteState.waiting_for_second_location)
    dp.register_callback_query_handler(process_second_stop_callback,
                                       lambda callback_query: callback_query.data.startswith('secondStop_'),
                                       state=RouteState.waiting_for_first_location)

    # find nearest stop
    dp.register_message_handler(nearest_stop_handler, text="🗺")
    # 🗺 - handlers
    dp.register_message_handler(process_location, content_types=types.ContentType.ANY,
                                state=NearStopState.waiting_for_location)

    # get current prices
    dp.register_message_handler(price_handler, text="💰")

    # leave comment
    dp.register_message_handler(comment_handler, text="💬")
    # 💬 - handlers
    dp.register_message_handler(leave_comment_process, content_types=types.ContentType.ANY,
                                state=CommentState.waiting_for_comment)
