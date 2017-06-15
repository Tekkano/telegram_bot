import requests
import config
from bs4 import BeautifulSoup
import html5lib
import telebot
from datetime import datetime, time, date


def get_page(group, week=''):
    if week:
        week = str(week) + '/'
    url = '{domain}/{group}/{week}raspisanie_zanyatiy_{group}.htm'.format(
        domain=config.domain, 
        week=week, 
        group=group)
    response = requests.get(url)
    web_page = response.text
    return web_page


def get_schedule(web_page, day):
    soup = BeautifulSoup(web_page, "html5lib")

    # Методы find и find_all позволяют найти теги с указанными атрибутами.
    schedule_table = soup.find("table", attrs={"id": day})

    # Время проведения занятий
    times_list = schedule_table.find_all("td", attrs={"class": "time"})
    times_list = [time.span.text for time in times_list]

    # Место проведения занятий
    locations_list = schedule_table.find_all("td", attrs={"class": "room"})
    locations_list = [room.span.text for room in locations_list]

    # Кабинеты
    cabs_list = schedule_table.find_all("dd", attrs={"class": "rasp_aud_mobile"})
    cabs_list = [cab.text for cab in cabs_list]

    # Название дисциплин и имена преподавателей
    lessons_list = schedule_table.find_all("td", attrs={"class": "lesson"})
    lessons_list = [lesson.text.split('\n\n') for lesson in lessons_list]
    lessons_list = [', '.join([info for info in lesson_info if info]) for lesson_info in lessons_list]

    return times_list, locations_list, lessons_list, cabs_list


bot = telebot.TeleBot(config.access_token)


def week_and_day(week_n, day_n):
    """
    Вспомогательная функция для get_near_lesson и get_tomorrow:
    определяет чётность недели, а также меняет неделю на следующую,
    если запрашиваем воскресенье (7day), и выдаёт понедельник (1day).
    """
    if (week_n % 2 == 0):  # если номер недели нацело делится на 2 то четная если нет то нечетная
    	week = 1
    else:
    	week = 2
    if day_n == '7day':  # если просим воскресенье > следующая неделя
    	day_n = '1day'  # если просим воскресенье > понедельник, в ином случае тот же
    	if week == 1:
    		week = 2
    	else:
    		week = 1
    return week, day_n


@bot.message_handler(commands=['monday','tuesday','wednesday','thursday','friday','saturday','sunday'])
def get_exact_day(message):
    """
    Расписание на один день недели для группы.
    /monday 1 K3142 - чётная неделя
    /tuesday 2 K3142 - нечётная неделя
    /wednesday 0 K3142 - обе недели вместе
    """
    day_in_week = {'/monday':'1day','/tuesday':'2day','/wednesday':'3day',\
                   '/thursday':'4day','/friday':'5day','/saturday':'6day',\
                   '/sunday':'7day'}
    day, week, group = message.text.split()
    if day in day_in_week.keys():  # /monday > day1, etc
        day = day_in_week.get(day)  # словарь day_in_week
    # try/except на случай, если занятий нет.
    try:
        web_page = get_page(group, week)
        times_list, locations_list, lessons_list, cabs_list = get_schedule(web_page, day)
        resp = ''
        for time, location, lesson, cab in zip(times_list, locations_list, lessons_list, cabs_list):
            resp += '{}, {}, {}, {}\n'.format(time, cab, location, lesson)
    except:
        resp = 'Занятий нет.'
    bot.send_message(message.chat.id, resp, parse_mode='HTML')


@bot.message_handler(commands=['tomorrow'])
def get_tomorrow(message):
    """
    Расписане для группы на завтра.
    /tomorrow K3142
    """
    _, group = message.text.split()
    today = datetime.now().isocalendar()  # ([0]2017,[1]week-22,[2]day-7)
    week_n = today[1]
    day_n = str(today[2]+1) + 'day'  # +1 тк нужен завтрашний день
    week, day = week_and_day(week_n, day_n)  # tuple (номер недели, номер завтрашнего дня + 'day')
    try:
        web_page = get_page(group, week)
        times_list, locations_list, lessons_list, cabs_list = get_schedule(web_page, day)
        resp = ''
        for time, location, lesson, cab in zip(times_list, locations_list, lessons_list, cabs_list):
            resp += '{}, {}, {}, {}\n'.format(time, cab, location, lesson)
    except:
        resp = 'Занятий завтра нет.'
    bot.send_message(message.chat.id, resp, parse_mode='HTML')


@bot.message_handler(commands=['all'])
def get_all_week(message):
    """
    Расписание на всю неделю для группы.
    /all 1 K3142 - чётная неделя
    /all 2 K3142 - нечётная неделя
    """
    weekday = ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота']
    _, week, group = message.text.split()
    web_page = get_page(group, week)
    resp = ''
    for d in range(1,7):  # выводим расписание для всех 6 учебных дней в неделе
        day = str(d)+'day'
        try:  # try/except на случай, если занятий нет.
            times_list, locations_list, lessons_list, cabs_list = get_schedule(web_page, day)
            display_day = weekday[d-1]  # [d-1] т.к. range начинает с 1, а индексы с 0
        except:
            continue  # если занятий нет, цикл for заново, уже со следующим значением
        resp += '\n\n<b>'+display_day+'</b>\n'  # если занятия есть и все прошло гладко, выводим имя дня недели
        for time, location, lesson, cab in zip(times_list, locations_list, lessons_list, cabs_list):
            resp += '{}, {}, {}, {}\n'.format(time, cab, location, lesson)
    bot.send_message(message.chat.id, resp, parse_mode='HTML')
  

@bot.message_handler(commands=['soon'])
def get_near_lesson(message):
    """
    Ближайшее занятие для группы.
    /soon K3142
    """
    _, group = message.text.split()
    today = datetime.now().isocalendar()  # ([0]2017,[1]week-22,[2]day-7)
    week_n = today[1]
    day_n = str(today[2])+'day'
    week, day = week_and_day(week_n, day_n)
    current_time = datetime.strftime(datetime.now(), "%H:%M")  # current datetime to fit %H:%M format
    web_page = get_page(group, week)
    times_list, locations_list, lessons_list, cabs_list = get_schedule(web_page, day)
    resp = 'Сейчас: {}\nБлижайшее занятие: \n'.format(current_time)
    for time, location, lesson, cab in zip(times_list, locations_list, lessons_list, cabs_list):
        try:
        	# create a datetime object by use of strptime() and a corresponding format string
        	# times_list = schedule_table.find_all("td", attrs={"class": "time"})... >
        	# from the data on the page (...<td class="time"><span>13:30-15:00</span>...)
        	# then format the datetime object back to a string by use of the same format string.
        	# ! time[:4] - slicing a string. We get the first 4 chars in a string (start time of lesson).
            class_time = datetime.strftime(datetime.strptime(time[:4],"%H:%M"),"%H:%M")
            if class_time > current_time:
                resp += '{}, {}, {}, {}\n'.format(time, cab, location, lesson)
                break
        except:
            resp = 'В ближайшее время пар нет :)'
    bot.send_message(message.chat.id, resp, parse_mode='HTML')


if __name__ == '__main__':
    bot.polling(none_stop=True)
