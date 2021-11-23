import json
import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

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

logger = logging.getLogger(__name__)


class BotException(Exception):
    """Исключение бота."""

    pass


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        logger.info('Отправка сообщения')
        return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TypeError:
        message = 'Ошибка токена'
        logger.error(message)
        raise TypeError(message)
    except telegram.error.BadRequest:
        message = 'Ошибка CHAT_ID'
        logger.error(message)
        raise telegram.error.BadRequest(message)
    except Exception as error:
        message = f'Ошибка {error}'
        logger.error(message)
        raise Exception(message)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту."""
    logger.info('Обращение к серверу')
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

    if homework_status.status_code != HTTPStatus.OK:
        logger.error(homework_status.json())
        raise BotException('Эндпоинт не отвечает')

    try:
        homework_status_json = homework_status.json()
    except json.JSONDecodeError:
        raise BotException("Ответ не в формате JSON")
    logger.info("Получен ответ от сервера")
    return homework_status_json


def check_response(response):
    """Проверка ответа API на корректность."""
    logger.info('Проверка ответа API на корректность')

    if isinstance(response, dict):
        if 'homeworks' not in response.keys():
            logger.error('Отсутствие ключа homeworks')
            raise BotException('Отсутствие ключа homeworks')

    if 'error' in response:
        logger.error(response['error'])
        raise BotException(response['error'])

    if response['homeworks'] is None:
        logger.info('Нет заданий')
        raise BotException('Нет заданий')

    if not isinstance(response['homeworks'], list):
        logger.info(f'{response["homeworks"]} Не является списком')
        raise BotException(f'{response["homeworks"]} Не является списком')
    logger.info('Проверка на корректность завершена')

    return response['homeworks']


def parse_status(homework):
    """Получение статуса домашней работы."""
    if 'homework_name' not in homework.keys():
        logger.error('Отсутствие ключа homework_name')
        raise BotException('Отсутствие ключа homework_name')

    if 'status' not in homework.keys():
        logger.error('Отсутствие ключа status')
        raise BotException('Отсутствие ключа status')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    verdict = HOMEWORK_STATUSES[homework.get('status')]

    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Недокументированный статус домашней работы')
        raise BotException('Неизвестный статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        logger.critical(
            'Отсутствие обязательных переменных окружения'
            'во время запуска бота')
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return 0
    current_timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if ((type(homeworks) is list) and homeworks):
                send_message(bot, parse_status(homeworks[0]))
            else:
                logger.info('Нет заданий')
                current_timestamp = response['current_date']
                time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
