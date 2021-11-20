import logging
import os
import time
import json
import telegram

import requests
from dotenv import load_dotenv
from telegram import Bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


bot = Bot(token=TELEGRAM_TOKEN)


class BotException(Exception):
    """Исключение бота"""

    pass


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        logging.info('Отправка сообщения')
        return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TypeError:
        message = 'Ошибка токена'
        logging.error(message)
        raise TypeError(message)
    except telegram.error.BadRequest:
        message = 'Ошибка CHAT_ID'
        logging.error(message)
        raise telegram.error.BadRequest(message)
    except Exception as error:
        message = f'Ошибка {error}'
        logging.error(message)
        raise Exception(message)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту."""
    logging.info('Обращение к серверу')
    timestamp = current_timestamp or int(time.time())
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers={'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise BotException(f'Ошибка в запросе: {error}')
    except TypeError as error:
        raise BotException(f'Неверные данные: {error}')
    except ValueError as error:
        raise BotException(f'Ошибка в значении: {error}')

    if homework_status.status_code != 200:
        logging.ERROR(homework_status.json())
        raise BotException('Эндпоинт не отвечает')

    try:
        homework_status_json = homework_status.json()
    except json.JSONDecodeError:
        raise BotException("Ответ не в формате JSON")
    logging.info("Получен ответ от сервера")
    return homework_status_json


def check_response(response):
    """Проверка ответа API на корректность."""
    logging.info('Проверка ответа API на корректность')

    if response['homeworks'] is None:
        logging.info('Нет заданий')
        raise BotException('Нет заданий')

    if not isinstance(response['homeworks'], list):
        logging.info(f'{response["homeworks"]} Не является списком')
        raise BotException(f'{response["homeworks"]} Не является списком')

    if 'error' in response:
        if 'error' in response['error']:
            logging.info(response['error']['error'])
            raise BotException(response['error']['error'])

    if 'code' in response:
        logging.info(response['message'])
        raise BotException(response['message'])
    logging.info('Проверка на корректность завершена')


def parse_status(homework):
    """Получение статуса домашней работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']

    verdict = HOMEWORK_STATUSES['homework_status']

    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Недокументированный статус домашней работы')
        raise BotException('Неизвестный статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if PRACTICUM_TOKEN is None or \
            TELEGRAM_TOKEN is None or \
            TELEGRAM_CHAT_ID is None:
        logging.critical(
            'Отсутствие обязательных переменных окружения'
            'во время запуска бота')
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return 0
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if ((type(homeworks) is list) and homeworks):
                send_message(bot, parse_status(homeworks[0]))
            else:
                logging.info('Нет заданий')
                current_timestamp = response['current_date']
                time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.critical(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
