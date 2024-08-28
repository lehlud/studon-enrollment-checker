from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from dotenv import load_dotenv
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import json
import time
import requests

load_dotenv()


def open_authed_studon_driver() -> WebDriver:
    driver = open_driver()
    driver.get('https://www.studon.fau.de/studon/saml.php')

    while not driver.current_url.startswith('https://www.sso.uni-erlangen.de'):
        driver.implicitly_wait(0.5)

    if os.getenv('IDM_USER') and os.getenv('IDM_PASS'):
        driver.find_element(By.ID, 'username')
        driver.find_element(By.ID, 'username').send_keys(os.getenv('IDM_USER'))
        driver.find_element(By.ID, 'password').send_keys(os.getenv('IDM_PASS'))
        driver.find_element(By.ID, 'submit_button').click()

    while not driver.current_url.startswith('https://www.studon.fau.de'):
        driver.implicitly_wait(0.5)

    return driver


def open_driver() -> WebDriver:
    options = webdriver.FirefoxOptions()
    options.add_argument('--headless')

    return webdriver.Firefox(options=options)


def get_course_info_using_driver(driver: WebDriver, course_id) -> tuple[str, str]:
    url = f'https://www.studon.fau.de/studon/goto.php?target=crs_{course_id}'

    driver.get(url)

    name = driver.find_element(
        By.CLASS_NAME, 'media-heading'
    ).text.strip()

    status = driver.find_element(
        By.XPATH, "//div[*[text()=\'Aufnahmeverfahren\']]/*[2]"
    ).text.strip()

    access = driver.find_element(
        By.XPATH, "//div[*[text()=\'Zugriff\']]/*[2]"
    ).text.strip()

    return name, status, access


def get_course_info(course_id):
    url = f'https://www.studon.fau.de/studon/goto.php?target=crs_{course_id}'
    response = requests.get(url)

    html = response.text

    # TODO


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
    if os.path.exists('cache.json'):
        with open('cache.json', 'r') as f:
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

    with open('cache.json', 'w') as f:
        json.dump(cache, f, indent=4)
