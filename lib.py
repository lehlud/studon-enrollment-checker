import ssl
import os
import json
import time
import requests
from pyquery import PyQuery
from dotenv import load_dotenv

import smtplib
from email.mime.text import MIMEText

load_dotenv()

cwd = os.path.dirname(os.path.realpath(__file__))
cache_file_path = os.path.join(cwd, 'cache.json')


def get_course_info(course_id) -> tuple[str, str, str] | None:
    url = f'https://www.studon.fau.de/studon/goto.php?target=crs_{course_id}'
    response = requests.get(url)

    if response.status_code != 200:
        return None

    pq = PyQuery(response.text)

    name = pq('.media-heading').children()[0].text.strip()
    status = pq(':contains(Aufnahmeverfahren)')[-1].getnext().text.strip()
    access = pq(':contains(Zugriff)')[-1].getnext().text.strip()

    return name, status, access


def try_notify_course_update(course_id, name, status, access):
    url = f'https://www.studon.fau.de/studon/goto.php?target=crs_{course_id}'

    try:
        if not os.getenv('SMTP_HOST') or not os.getenv('SMTP_PORT') or not os.getenv('SMTP_USER') or not os.getenv('SMTP_PASS') or not os.getenv('SMTP_DEST'):
            raise Exception()

        message = MIMEText(f'<html><head></head><body><p>Der Kurs <a href="{url}">{name}</a> hat Änderungen:<br>Status: <b>{status}</b><br>Zugriff: <b>{access}</b></p></body></html>', 'html')  # nopep8
        message['Subject'] = '[StudOn Enroller] ' + name
        message['From'] = os.getenv('SMTP_USER')
        message['To'] = os.getenv('SMTP_DEST')

        context = ssl.create_default_context()
        with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls(context=context)
            server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASS'))
            server.sendmail(
                os.getenv('SMTP_USER'),
                os.getenv('SMTP_DEST'),
                message.as_string(),
            )

            server.quit()

    except Exception as e:
        print(e)

        print('unable to notify course availability: ' +
              f'{course_id=}, {name=}, {status=}, {access=}')
        return


def _get_course_cache() -> dict[int, dict]:
    data = {}
    if os.path.exists(cache_file_path):
        with open(cache_file_path, 'r') as f:
            data = json.load(f)
    return data


def get_cached_course(course_id) -> str:
    cache = _get_course_cache()
    course = cache.get(str(course_id), {})
    return course.get('status'), course.get('access')


def cache_course(course_id, status, access):
    cache = _get_course_cache()

    cache[str(course_id)] = {
        'timestamp': int(time.time()),
        'status': status,
        'access': access
    }

    with open(cache_file_path, 'w') as f:
        json.dump(cache, f, indent=4)
