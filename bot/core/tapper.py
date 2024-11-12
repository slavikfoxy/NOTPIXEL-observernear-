from datetime import datetime, timedelta, timezone
from dateutil import parser
from time import time
from urllib.parse import unquote, quote
import urllib.request  
import re
from copy import deepcopy
from PIL import Image
import io
import os
import math
import sys
import traceback

from json import dump as dp, loads as ld
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types

import websockets
import asyncio
import random
import string
import brotli
import base64
import secrets
import uuid
import aiohttp
import json

from .agents import generate_random_user_agent
from .headers import headers, headers_notcoin
from .helper import format_duration

from bot.config import settings
from bot.utils import logger
from bot.utils.logger import SelfTGClient
from bot.exceptions import InvalidSession

self_tg_client = SelfTGClient()

class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None
        self.first_run = None
        self.game_service_is_unavailable = False
        self.already_joined_squad_channel = None
        self.user = None
        self.updated_pixels = {}
        self.socket = None
        self.socket_task = None
        self.last_balance = 0
        self.filename = 'Balances.txt'
        self.IMAGE_LINK = settings.IMAGE_LINK
        self.REF_ID = settings.REF_ID
        self.x_offset = settings.X_OFFSET
        self.y_offset = settings.Y_OFFSET
        self.extra = 0
        self.missPx = 0
        self.nextline = False
        self.time_reset = False
        self.current_line = 0
        self.error_draw = False

        self.session_ug_dict = self.load_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()
        headers_notcoin['User-Agent'] = headers['User-Agent']

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def info(self, message):
        from bot.utils import info
        info(f"<light-yellow>{self.session_name}</light-yellow> | ℹ️ {message}")

    def debug(self, message):
        from bot.utils import debug
        debug(f"<light-yellow>{self.session_name}</light-yellow> | ⚙️ {message}")

    def warning(self, message):
        from bot.utils import warning
        warning(f"<light-yellow>{self.session_name}</light-yellow> | ⚠️ {message}")

    def error(self, message):
        from bot.utils import error
        error(f"<light-yellow>{self.session_name}</light-yellow> | 😢 {message}")

    def critical(self, message):
        from bot.utils import critical
        critical(f"<light-yellow>{self.session_name}</light-yellow> | 😱 {message}")

    def success(self, message):
        from bot.utils import success
        success(f"<light-yellow>{self.session_name}</light-yellow> | ✅ {message}")

    async def save_or_update_session(self, balance):
        sessions = {}
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as file:
                for line in file:
                    # Skip empty or malformed lines
                    if ',' not in line:
                        continue
                    try:
                        name, bal = line.strip().split(',')
                        sessions[name] = float(bal)
                    except ValueError:
                        print(f"Skipping malformed line: {line.strip()}")
        
        sessions[self.session_name] = balance
        
        with open(self.filename, 'w', encoding='utf-8') as file:
            for name, bal in sessions.items():
                file.write(f"{name},{bal}\n")
    
    async def get_total_balance(self):
        total_balance = 0
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as file:
                for line in file:
                    _, bal = line.strip().split(',')
                    total_balance += float(bal)
        return total_balance

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            self.success(f"User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            if 'https://' in self.REF_ID:
                match = re.search(r'startapp=([\w_]+)', self.REF_ID)
                if match:
                    self.start_param = match.group(1)
            else:
                self.start_param = self.REF_ID

            peer = await self.tg_client.resolve_peer('notpixel')
            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="app")

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotApp,
                platform='android',
                write_allowed=True,
                start_param=self.start_param
            ))

            auth_url = web_view.url

            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            try:
                if self.user_id == 0:
                    information = await self.tg_client.get_me()
                    self.user_id = information.id
                    self.first_name = information.first_name or ''
                    self.last_name = information.last_name or ''
                    self.username = information.username or ''
            except Exception as e:
                print(e)

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            self.error(f"Session error during Authorization: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=10)

        except Exception as error:
            self.error(
                f"Unknown error during Authorization: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)

    async def get_tg_web_data_not(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('notgames_bot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    self.warning(f"FloodWait {fl}")
                    self.info(f"Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="squads")

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotApp,
                platform='android',
                write_allowed=True,
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            self.error(f"Unknown error during getting web data for squads: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)

    def is_night_time(self):
        night_start = settings.NIGHT_TIME[0]
        night_end = settings.NIGHT_TIME[1]

        # Get the current hour
        current_hour = datetime.now().hour

        if current_hour >= night_start or current_hour < night_end:
            return True

        return False

    def time_until_morning(self):
        morning_time = datetime.now().replace(hour=settings.NIGHT_TIME[1], minute=0, second=0, microsecond=0)

        if datetime.now() >= morning_time:
            morning_time += timedelta(days=1)

        time_remaining = morning_time - datetime.now()

        return time_remaining.total_seconds() / 60

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            self.info(f"Proxy IP: {ip}")
        except Exception as error:
            self.error(f"Proxy: {proxy} | Error: {error}")

    async def get_user_info(self, http_client: aiohttp.ClientSession, show_error_message: bool):
        ssl = settings.ENABLE_SSL
        err = None

        for _ in range(2):
            try:
                response = await http_client.get("https://notpx.app/api/v1/users/me", ssl=ssl)

                response.raise_for_status()

                data = await response.json()

                err = None

                return data
            except Exception as error:
                ssl = not ssl
                self.info(f"First get user info request not always successful, retrying..")
                err = error
                continue

        if err != None and show_error_message == True:
            self.error(f"Unknown error during get user info: <light-yellow>{err}</light-yellow>")
            return None

    async def get_status(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get('https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)

            response.raise_for_status()

            data = await response.json()

            return data
        except Exception as error:
            self.error(f"Unknown error during processing status: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)
            return None

    async def get_balance(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get('https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)

            response.raise_for_status()

            data = await response.json()

            return data['userBalance']
        except Exception as error:
            self.error(f"Unknown error during processing balance: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)
            return None

    async def get_image(self, http_client, url, image_headers=None):
        try:
            # Якщо image_headers не передані, використовуємо порожній словник
            async with http_client.get(url, headers=image_headers) as response:
                if response.status == 200:
                    # Отримуємо MIME-тип
                    content_type = response.headers.get('Content-Type', '').lower()

                    # Перевіряємо, чи це зображення
                    if 'image' not in content_type:
                        raise Exception(f"URL не содержит изображения. MIME-тип: {content_type}")

                    # Читаємо дані зображення
                    img_data = await response.read()

                    # Перетворюємо байти у зображення
                    img = Image.open(io.BytesIO(img_data))

                    # Визначаємо формат зображення на основі MIME-типу
                    if 'jpeg' in content_type:
                        format = 'JPEG'
                    elif 'png' in content_type:
                        format = 'PNG'
                    elif 'gif' in content_type:
                        format = 'GIF'
                    elif 'webp' in content_type:
                        format = 'WEBP'
                    else:
                        raise Exception(f"Невідомий формат зображення: {content_type}")

                    #save_path = os.path.join('downloaded_images', f"downloaded_image.{format.lower()}")
                    # Створюємо папку, якщо вона не існує
                    #os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    # Зберігаємо зображення у локальну папку
                    #img.save(save_path, format=format)
                    #self.info(f"Image saved to {save_path}")

                    return img
                else:
                    raise Exception(f"Failed to download image from {url}, status: {response.status}")
        except Exception as error:
            self.error(f"Error during loading image from url: {url} | Error: {error}")
            return None

    async def send_draw_request(self, http_client: aiohttp.ClientSession, update):
        x, y, color = update

        pixelId = int(f'{y}{x}')+1

        payload = {
            "pixelId": pixelId,
            "newColor": color
        }

        draw_request = await http_client.post(
            'https://notpx.app/api/v1/repaint/start',
            json=payload,
            ssl=settings.ENABLE_SSL
        )

        draw_request.raise_for_status()

        data = await draw_request.json()
        balance = data.get('balance', 'unknown')
        difference_pix = 0
        try:
            if isinstance(balance, str):
                balance = float(balance.replace(',', ''))  
            elif isinstance(balance, (int, float)):
                balance = float(balance) 
            difference_pix = balance - self.last_balance
            
            self.last_balance = balance
            
        except ValueError:
            self.error(f"ValueError, error convert difference_pix to float.")
        if difference_pix == 0:
            self.missPx +=1
            #await self.read_and_update_line('templates.txt', self.current_line, True)
        else:
            self.missPx = 0
        self.success(f"Painted (X: <cyan>{x}</cyan>, Y: <cyan>{y}</cyan>) with color <light-blue>{color}</light-blue> 🎨️ | Balance <light-green>{'{:,.3f}'.format(data.get('balance', 'unknown'))}</light-green> <red>(+ {round(difference_pix)} pix) </red>  🔳")

    async def read_and_update_line(self, filename, line_number= None, new_extra_value=None, bestline=None):
        try:
            if os.path.exists('templates.txt'):
                with open(filename, 'r') as file:
                    lines = file.readlines()
                if bestline == True:
                    intline = 0
                    min_value = None
                    returnnumline = 0
                    for line in lines:
                        parts = line.strip().split(", ")
                        if len(parts) == 5:
                            try:
                                extra_value = int(parts[-1])
                                if min_value is None:   
                                    min_value = extra_value
                                    returnnumline = intline
                                if extra_value < min_value:
                                    min_value = extra_value
                                    returnnumline = intline
                            except ValueError:
                                self.error("Error find bestline")
                        intline +=1
                    return returnnumline
                if line_number != None and bestline == None:
                    
                    if 0 <= line_number < len(lines):
                        line = lines[line_number].strip()
                        parts = line.split(", ")

                        if new_extra_value is not None and len(parts) == 5:
                            parts[-1] = str(int(parts[-1]) + 1)
                            lines[line_number] = ", ".join(parts) + "\n"  

                            with open(filename, 'w') as file:
                                file.writelines(lines)

                        if new_extra_value == None and line_number != None and bestline == None:
                            if len(parts) == 5:
                                    self.IMAGE_LINK, self.REF_ID, self.x_offset, self.y_offset, self.extra = parts
                                    self.x_offset = int(self.x_offset)
                                    self.y_offset = int(self.y_offset)
                                    self.extra = int(self.extra)

                    else:
                        self.error("(read_and_update_line) Line number out of range.")
            return len(lines)
        except Exception as e:
            self.error(f"read_and_update_line error {traceback.format_exc()}")
            return None
        

    async def send_pumking(self, http_client: aiohttp.ClientSession, update):
        x, y = update
        pixelId = int(f'{y}{x}')+1
        payload = {
            "pixelId": pixelId,
            "type": 7
        }

        draw_request = await http_client.post(
            'https://notpx.app/api/v1/repaint/special',
            json=payload,
            ssl=settings.ENABLE_SSL
        )

        draw_request.raise_for_status()
        await asyncio.sleep(delay=1)
        balance = await self.get_balance(http_client=http_client)
        difference_pix = 0
        try:
            if isinstance(balance, str):
                balance = float(balance.replace(',', ''))  
            elif isinstance(balance, (int, float)):
                balance = float(balance) 
            difference_pix = balance - self.last_balance
            
            self.last_balance = balance
        except ValueError:
            self.error(f"ValueError, error convert difference_pix to float.")
        self.success(f"Painted (X: <cyan>{x}</cyan>, Y: <cyan>{y}</cyan>) with PUMKING 🎨️ | Balance <light-green>{balance:,.3f}</light-green> <red>(+ {round(difference_pix)} pix) </red>  🔳")


    async def Download_template(self, http_client: aiohttp.ClientSession):
        method_download_flag = False
        if settings.FORCE_FILE:
            try:
                save_path = os.path.join(settings.LOCAL_LINK_TO_FILE)
                with open(save_path, 'rb') as f:
                    img_data = f.read()
                    img = Image.open(io.BytesIO(img_data))
                original_image = img
                if not original_image:
                    return None
                return original_image
            except Exception as e:
                self.info(f"Ошибка загрузки локального файла (LOCAL_LINK_TO_FILE) - {settings.LOCAL_LINK_TO_FILE}| {e} | {traceback.format_exc()}")
            
        else:
            try:
                #self.info(f"Способ загрузки шаблона 1 - urllib.request")
                with urllib.request.urlopen(self.IMAGE_LINK) as response:
                    img_data = response.read()
                    img = Image.open(io.BytesIO(img_data))
                    try:
                        if not os.path.exists("images"):
                            os.makedirs("images")
                        image_name = os.path.basename(self.IMAGE_LINK)
                        img.save(os.path.join("images", image_name))
                    except Exception as error:
                        self.error(f"Error during image download and save: {error}")
                original_image = img
                method_download_flag = True
                return original_image
                if not original_image:
                    return None
            except urllib.error.HTTPError as e:
                self.error(f"Ошибка {e.code} - {e.reason}.")
            
            if not method_download_flag:
                try:
                    #self.info(f"Способ загрузки шаблона 2 - get_image")
                    original_image_url = self.IMAGE_LINK
                    pattern = r'://([^/]+)/'
                    match = re.search(pattern, original_image_url)
                    image_headers = deepcopy(headers)
                    image_headers['Host'] = match.group(1)
                    original_image = await self.get_image(http_client, original_image_url, image_headers=image_headers)
                    try:
                        if original_image:
                            image_name = os.path.basename(self.IMAGE_LINK)
                            if not os.path.exists("images"):
                                os.makedirs("images")
                            save_path = os.path.join("images", image_name)
                            original_image.save(save_path)
                    except Exception as error:
                        self.error(f"Error during image download and save: {error}")
                    if original_image:
                        method_download_flag = True
                        return original_image
                except Exception as e:
                    self.error(f"Ошибка при загрузке изображения - {e}")
            
            if not method_download_flag:
                try:
                    self.info(f"Способ загрузки шаблона 3 - локальный файл - os.path.join")
                    pattern = r"/([^/]+\.png)$"
                    match = re.search(pattern, self.IMAGE_LINK)
                    save_path = os.path.join("images", match.group(1))
                    with open(save_path, 'rb') as f:
                        img_data = f.read()
                        img = Image.open(io.BytesIO(img_data))
                    original_image = img
                    if not original_image:
                        return None
                    return original_image
                except Exception as e:
                    self.error(f"Ошибка {e} - Отсутствует файл или указано неверное название файла.")

    async def draw(self, http_client: aiohttp.ClientSession):
        try:
            self.error_draw = True
            response = await http_client.get('https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)
            response.raise_for_status()
            data = await response.json()
            charges = data['charges'] 
            balance_str = data.get('userBalance', 'unknown')
            self.last_balance = float(balance_str)
            #if not data.get('tasks', {}).get('pumpkin'):
                #await self.pumking_frirs_start(http_client=http_client)
            #self.info(f"data good : <cyan>{data['goods']}</cyan> ⚡️")
            #PUMKING
            if '7' in data.get('goods', {}):
                pumking = data['goods']['7']
                if charges > 0:
                    self.info(f"Pumking: <cyan>{pumking}</cyan> ⚡️")
                else:
                    self.info(f"No energy ⚡️")
                    return None
                    
                while pumking > 0:
                    updated_x = random.randint(10, 990)
                    updated_y = random.randint(10, 990)
                    await self.send_pumking(
                        http_client=http_client,
                        update=(updated_x, updated_y)
                    )
                
                    pumking -= 1

            #///PUMKING
            if charges > 0:
                self.info(f"Energy: <cyan>{charges}</cyan> ⚡️")
            else:
                self.info(f"No energy ⚡️")
                return None
            
            if settings.INFO:
                self.info(f"link - {self.IMAGE_LINK}")
                self.info(f"REF_ID({settings.USE_REF}) - {self.REF_ID}, x:{self.x_offset} y:{self.y_offset}")
                #self.info(f"ENABLE_DRAW_ART - {settings.ENABLE_DRAW_ART}, ENABLE_EXPERIMENTAL_X3_MODE - ({settings.ENABLE_EXPERIMENTAL_X3_MODE})")
            # Download Image

            original_image = await self.Download_template(http_client=http_client)

            while charges > 0:
                await asyncio.sleep(delay=random.randint(1, 4))
                try:
                    if hasattr(settings, 'MISSPX_TO_NEXT_TEMPLATES'):
                        MISSPX_TO_NEXT_TEMPLATES = settings.MISSPX_TO_NEXT_TEMPLATES-1
                    else: 
                        MISSPX_TO_NEXT_TEMPLATES = 5
                    if self.missPx == MISSPX_TO_NEXT_TEMPLATES:
                        self.nextline = True
                        self.time_reset = True
                        self.missPx = 0
                        break
                except Exception as e:
                    self.error(f"Ошибка {e} - Отсутствует MISSPX_TO_NEXT_TEMPLATES.")
                
                # Основной шаблон 1000 х 1000
                current_image_url = 'https://image.notpx.app/api/v2/image'
                image_headers = deepcopy(headers)
                image_headers['Host'] = 'image.notpx.app'
                current_image = await self.get_image(http_client, current_image_url, image_headers=image_headers)
                if not current_image:
                    return None

                if current_image and original_image:
                    # Порівняння зображень і отримання змінених пікселів
                    changes = await self.compare_images(current_image, original_image, self.x_offset, self.y_offset)
                    change = random.choice(changes)
                    num_changes = len(changes)
                    self.info(f"Количество пикселей на шаблоне для перекраски - {num_changes} ...")
                    updated_x, updated_y, original_pixel_color = change
                    await self.send_draw_request(
                        http_client=http_client,
                        update=(updated_x, updated_y, original_pixel_color)
                    )
                
                    # Зменшуємо кількість доступної енергії
                    charges -= 1
                    self.error_draw = False
            await self.save_or_update_session(balance_str)
        except Exception as e:
            error_message = f"Websocket error during painting: {str(e)}"
            detailed_error = traceback.format_exc()  # Отримуємо повний текст помилки з трасуванням
            self.error(f"{error_message}\nDetailed error:\n{detailed_error}")
        except Exception as error:
            self.warning(f"Unknown error during painting: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)
            await self.draw(http_client=http_client)
            

    async def draw_random(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get('https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)
            response.raise_for_status()
            data = await response.json()
            charges = data['charges'] 
            balance_str = data.get('userBalance', 'unknown')
            self.last_balance = float(balance_str)

            if charges > 0:
                self.info(f"Energy: <cyan>{charges}</cyan> ⚡️")
            else:
                self.info(f"No energy ⚡️")
                return None
            
            if settings.INFO:
                self.info(f"link - {self.IMAGE_LINK}")
                self.info(f"REF_ID({settings.USE_REF}) - {self.REF_ID}, x:{self.x_offset} y:{self.y_offset}")

            original_image = await self.Download_template(http_client=http_client)

            while charges > 0:
                await asyncio.sleep(delay=random.randint(1, 4))
                width, height = original_image.size
                x = random.randint(0, width - 5)
                y = random.randint(0, height - 5)
                image_pixel = original_image.getpixel((x, y))
                image_hex_color = '#{:02x}{:02x}{:02x}'.format(*image_pixel).upper()
                self.info(f"Рисуем наугад ))) ... x = {settings.X_OFFSET + width} || y = {settings.Y_OFFSET + height}|| {x + settings.X_OFFSET} | {y + settings.Y_OFFSET} | {image_hex_color}")
                await self.send_draw_request(
                    http_client=http_client,
                    update=(x + settings.X_OFFSET, y + settings.Y_OFFSET, image_hex_color.upper())
                )
                charges -= 1
            await self.save_or_update_session(balance_str)
        except Exception as e:
            error_message = f"Websocket error during painting: {str(e)}"
            detailed_error = traceback.format_exc()  # Отримуємо повний текст помилки з трасуванням
            self.error(f"{error_message}\nDetailed error:\n{detailed_error}")
        except Exception as error:
            self.warning(f"Unknown error during painting: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)
            await self.draw_random(http_client=http_client)


    async def compare_images(self, base_image, overlay_image, x_offset, y_offset, threshold=30):
    #Сравнивает два изображения и возвращает список измененных пикселей, игнорируя небольшие смещения цвета.
        changes = []
        
        def color_distance(c1, c2):
            #Вычисляет евклидово расстояние между двумя цветами."
            return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
        
        for x in range(overlay_image.width):
            for y in range(overlay_image.height):
                base_pixel = base_image.getpixel((x + x_offset, y + y_offset))
                overlay_pixel = overlay_image.getpixel((x, y))
                
                # Вычисляем расстояние между цветами
                distance = color_distance(base_pixel, overlay_pixel)
                
                # Если расстояние между цветами больше порога, считаем, что пиксели разные
                if distance > threshold:
                    # Конвертируем пиксель в формат #RRGGBB
                    overlay_pixel_color = '#{:02x}{:02x}{:02x}'.format(*overlay_pixel).upper()
                    
                    # Добавляем измененный пиксель и его цвет
                    changes.append((x + x_offset, y + y_offset, overlay_pixel_color))
        
        return changes


    async def upgrade(self, http_client: aiohttp.ClientSession):
        try:
            while True:
                response = await http_client.get('https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)

                response.raise_for_status()

                data = await response.json()

                boosts = data['boosts']

                self.info(f"Boosts Levels: Energy Limit - <cyan>{boosts['energyLimit']}</cyan> ⚡️| Paint Reward - <light-green>{boosts['paintReward']}</light-green> 🔳 | Recharge Speed - <magenta>{boosts['reChargeSpeed']}</magenta> 🚀")

                if boosts['energyLimit'] >= settings.ENERGY_LIMIT_MAX and boosts['paintReward'] >= settings.PAINT_REWARD_MAX and boosts['reChargeSpeed'] >= settings.RE_CHARGE_SPEED_MAX:
                    return

                for name, level in sorted(boosts.items(), key=lambda item: item[1]):
                    if name == 'energyLimit' and level >= settings.ENERGY_LIMIT_MAX:
                        continue

                    if name == 'paintReward' and level >= settings.PAINT_REWARD_MAX:
                        continue

                    if name == 'reChargeSpeed' and level >= settings.RE_CHARGE_SPEED_MAX:
                        continue

                    if name not in settings.BOOSTS_BLACK_LIST:
                        try:
                            res = await http_client.get(f'https://notpx.app/api/v1/mining/boost/check/{name}', ssl=settings.ENABLE_SSL)

                            res.raise_for_status()

                            self.success(f"Upgraded boost: <cyan>{name}</<cyan> ⬆️")

                            await asyncio.sleep(delay=random.randint(2, 5))
                        except Exception as error:
                            self.warning(f"Not enough money to keep upgrading. 💰")

                            await asyncio.sleep(delay=random.randint(5, 10))
                            return

        except Exception as error:
            self.error(f"Unknown error during upgrading: <light-yellow>{error}</light-yellow>")
            await asyncio.sleep(delay=3)

    async def run_tasks(self, http_client: aiohttp.ClientSession):
        try:
            res = await http_client.get('https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)

            await asyncio.sleep(delay=random.randint(1, 3))

            res.raise_for_status()

            data = await res.json()

            tasks = data['tasks'].keys()

            # 'nikolai', fetch-запит
            if 'nikolai' in tasks:
                async with http_client.post(
                    'https://plausible.joincommunity.xyz/api/event',
                    headers={
                        "accept": "*/*",
                        "content-type": "text/plain",
                    },
                    json={
                        "n": "task_nikolai",
                        "u": "https://app.notpx.app/claiming",
                        "d": "notpx.app",
                        "r": None,
                        "p": {"country": "PL"}
                    },
                    ssl=settings.ENABLE_SSL
                ) as response:
                    response.raise_for_status()
                    self.success("Executed task_nikolai event successfully.")


            for task in settings.TASKS_TODO_LIST:
                if self.user != None and task == 'premium' and not 'isPremium' in self.user:
                    continue

                if self.user != None and task == 'leagueBonusSilver' and self.user['repaints'] < 9:
                    continue

                if self.user != None and task == 'leagueBonusGold' and self.user['repaints'] < 129:
                    continue

                if self.user != None and task == 'leagueBonusPlatinum' and self.user['repaints'] < 2049:
                    continue

                if task not in tasks:
                    if re.search(':', task) is not None:
                        split_str = task.split(':')
                        social = split_str[0]
                        name = split_str[1]

                        if social == 'channel' and settings.ENABLE_JOIN_TG_CHANNELS:
                            continue

                        response = await http_client.get(f'https://notpx.app/api/v1/mining/task/check/{social}?name={name}', ssl=settings.ENABLE_SSL)
                    else:
                        response = await http_client.get(f'https://notpx.app/api/v1/mining/task/check/{task}', ssl=settings.ENABLE_SSL)

                    response.raise_for_status()

                    data = await response.json()

                    status = data[task]

                    if status:
                        self.success(f"Task requirements met. Task <cyan>{task}</cyan> completed ✔")

                        current_balance = await self.get_balance(http_client=http_client)

                        if current_balance is None:
                            self.info(f"Current balance: Unknown 🔳")
                        else:
                            self.info(f"Balance: <light-green>{'{:,.3f}'.format(current_balance)}</light-green> 🔳")
                    else:
                        self.warning(f"Task requirements were not met <cyan>{task}</cyan>")

                    await asyncio.sleep(delay=random.randint(3, 7))

        except Exception as error:
            self.error(f"Unknown error during processing tasks: <light-yellow>{error}</light-yellow>")

    async def claim_mine(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(f'https://notpx.app/api/v1/mining/status', ssl=settings.ENABLE_SSL)

            response.raise_for_status()

            response_json = await response.json()

            await asyncio.sleep(delay=random.randint(4, 6))

            for _ in range(2):
                try:
                    response = await http_client.get(f'https://notpx.app/api/v1/mining/claim', ssl=settings.ENABLE_SSL)

                    response.raise_for_status()

                    response_json = await response.json()
                except Exception as error:
                    self.info(f"First claiming not always successful, retrying..")
                else:
                    break

            return response_json['claimed']
        except Exception as error:
            self.error(f"Unknown error during claiming reward: <light-yellow>{error}</light-yellow>")

            await asyncio.sleep(delay=3)

    async def join_squad(self, http_client=aiohttp.ClientSession, user={}):
        try:
            current_squad_slug = user['squad']['slug']

            if settings.ENABLE_AUTO_JOIN_TO_SQUAD_CHANNEL and settings.SQUAD_SLUG and current_squad_slug != settings.SQUAD_SLUG:
                try:
                    if self.already_joined_squad_channel != settings.SQUAD_SLUG:
                        if not self.tg_client.is_connected:
                            await self.tg_client.connect()
                            await asyncio.sleep(delay=2)

                        res = await self.tg_client.join_chat(settings.SQUAD_SLUG)

                        if res:
                            self.success(f"Successfully joined to squad channel: <magenta>{settings.SQUAD_SLUG}</magenta>")

                        self.already_joined_squad_channel = settings.SQUAD_SLUG

                        await asyncio.sleep(delay=2)

                        if self.tg_client.is_connected:
                            await self.tg_client.disconnect()

                except Exception as error:
                    self.error(f"Unknown error when joining squad channel <cyan>{settings.SQUAD_SLUG}</cyan>: <light-yellow>{error}</light-yellow>")

                squad = settings.SQUAD_SLUG
                local_headers = deepcopy(headers_notcoin)

                local_headers['X-Auth-Token'] = "Bearer null"

                response = await http_client.post(
                   'https://api.notcoin.tg/auth/login',
                    headers=local_headers,
                    json={"webAppData": self.tg_web_data_not}
                )

                response.raise_for_status()

                text_data = await response.text()

                json_data = json.loads(text_data)

                accessToken = json_data.get("data", {}).get("accessToken", None)

                if not accessToken:
                    self.warning(f"Error during join squads: can't get an authentication token to enter to the squad")
                    return

                local_headers['X-Auth-Token'] = f'Bearer {accessToken}'
                info_response = await http_client.get(
                    url=f'https://api.notcoin.tg/squads/by/slug/{squad}',
                    headers=local_headers
                )

                info_json = await info_response.json()
                chat_id = info_json['data']['squad']['chatId']

                join_response = await http_client.post(
                    f'https://api.notcoin.tg/squads/{squad}/join',
                    headers=local_headers,
                    json={'chatId': chat_id}
                )

                if join_response.status in [200, 201]:
                    self.success(f"Successfully joined squad: <magenta>{squad}</magenta>")
                else:
                    self.warning(f"Something went wrong when joining squad: <magenta>{squad}</magenta>")
        except Exception as error:
            self.error(f"Unknown error when joining squad: <light-yellow>{error}</light-yellow>")

            await asyncio.sleep(delay=3)

    async def create_socket_connection(self, http_client: aiohttp.ClientSession):
        uri = "wss://notpx.app/api/v2/image/ws"

        try:
            socket = await http_client.ws_connect(uri)

            self.socket = socket

            self.info("WebSocket connected successfully")

            return socket

        except Exception as e:
            self.error(f"WebSocket connection error: {e}")
            return None

    async def run(self, proxy: str | None) -> None:
        while True:
            Numlines = 0
            if settings.TEMPLATES_FILE_MANUAL or self.nextline == True:
                Numlines = await self.read_and_update_line('templates.txt')
                if self.nextline == True and self.current_line < Numlines:
                    if self.error_draw == True:
                        self.current_line +=1
                    else:
                        self.current_line = await self.read_and_update_line('templates.txt', None, None, True)
                self.info(f"Используемой шаблон с файла - {self.current_line+1}.")
                await self.read_and_update_line('templates.txt', self.current_line)
            if settings.USE_RANDOM_DELAY_IN_RUN:
                random_delay = random.randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
                self.info(f"Bot will start in <ly>{random_delay}s</ly>")
                await asyncio.sleep(random_delay)
    
            access_token = None
            refresh_token = None
            login_need = True
    
            proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
    
            #http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
            async with CloudflareScraper(headers=headers, connector=proxy_conn) as http_client:

                if proxy:
                    await self.check_proxy(http_client=http_client, proxy=proxy)
        
                access_token_created_time = 0
                token_live_time = random.randint(500, 900)
        
                self.time_reset = False
                #self.success("while Start True")
                try:
                    if time() - access_token_created_time >= token_live_time:
                        login_need = True

                    if login_need:
                        if "Authorization" in http_client.headers:
                            del http_client.headers["Authorization"]

                        self.tg_web_data = await self.get_tg_web_data(proxy=proxy)
                        self.tg_web_data_not = await self.get_tg_web_data_not(proxy=proxy)

                        http_client.headers['Authorization'] = f"initData {self.tg_web_data}"

                        access_token_created_time = time()
                        token_live_time = random.randint(500, 900)

                        if self.first_run is not True:
                            self.success("Logged in successfully")
                            self.first_run = True

                        login_need = False

                    await asyncio.sleep(delay=3)

                except Exception as error:
                    self.error(f"Unknown error during login. Waiting 30 seconds before retrying: <light-yellow>{error}</light-yellow>")
                    await asyncio.sleep(delay=30)
                    continue  

                try:
                    user = await self.get_user_info(http_client=http_client, show_error_message=True)

                    await asyncio.sleep(delay=2)

                    if user is not None:
                        #if settings.ENABLE_EXPERIMENTAL_X3_MODE:
                            #self.socket = await self.create_socket_connection(http_client=http_client)

                        self.user = user
                        current_balance = await self.get_balance(http_client=http_client)
                        repaints = user['repaints']
                        league = user['league']

                        if current_balance is None:
                            self.info(f"Current balance: Unknown 🔳")
                        else:
                            self.info(f"Balance: <light-green>{'{:,.3f}'.format(current_balance)}</light-green> 🔳 | Repaints: <magenta>{repaints}</magenta> 🎨️ | League: <cyan>{league.capitalize()}</cyan> 🏆")
                            await self.save_or_update_session(current_balance)

                        if settings.ENABLE_AUTO_JOIN_TO_SQUAD:
                            await self.join_squad(http_client=http_client, user=user)

                        if settings.ENABLE_AUTO_TASKS:
                            await self.run_tasks(http_client=http_client)

                        if settings.ENABLE_AUTO_DRAW:
                            #await self.draw(http_client=http_client)
                            await self.draw_random(http_client=http_client)
                            #self.info(f"draw временно недоступен. Пишем в config DRAW_RANDOM: bool = True ")
                        if settings.DRAW_RANDOM:
                            await self.draw_random(http_client=http_client)

                        if settings.ENABLE_AUTO_UPGRADE:
                            status = await self.upgrade(http_client=http_client)
                            if status is not None:
                                self.info(f"Claim reward: <light-green>{status}</light-green> ✔️")

                        if settings.ENABLE_CLAIM_REWARD:
                            reward = await self.claim_mine(http_client=http_client)
                            if reward is not None:
                                self.info(f"Claim reward: <light-green>{'{:,.3f}'.format(reward)}</light-green> 🔳")
                    else:
                        self.time_reset = True

                    all_balance = await self.get_total_balance()
                    self.info(f"Баланс всех аккаунтов: <red>{'{:,.3f}'.format(all_balance)}</red>")

                    sleep_time = random.randint(settings.SLEEP_TIME_IN_MINUTES[0], settings.SLEEP_TIME_IN_MINUTES[1])

                    is_night = False
                    if not self.time_reset:
                        if settings.DISABLE_IN_NIGHT:
                            is_night = self.is_night_time()
        
                        if is_night:
                            sleep_time = self.time_until_morning()
        
                        if is_night:
                            self.info(f"sleep {int(sleep_time)} minutes to the morning ({settings.NIGHT_TIME[1]} hours) 💤")
                        else:
                            self.info(f"sleep {int(sleep_time)} minutes between cycles 💤")
        
                        if self.socket != None:
                            try:
                                await self.socket.close()
                                self.info(f"WebSocket closed successfully")
                            except Exception as error:
                                self.error(f"Unknown error during closing socket: <light-yellow>{error}</light-yellow>")
                        
                        await asyncio.sleep(delay=sleep_time*60)
                    else:
                        self.time_reset = False
                        if self.nextline == True:
                            self.info(f"Перезапуск шаблона...")
                            await asyncio.sleep(delay=3)
                        elif hasattr(settings, 'FLOOD_WAIT_420_TIME'):
                            self.info(f"Waiting {settings.FLOOD_WAIT_420_TIME} seconds before retrying...")
                            await asyncio.sleep(delay=settings.FLOOD_WAIT_420_TIME)
                        else:
                            self.info(f"Waiting 20 seconds before retrying...")
                            await asyncio.sleep(delay=20)
                        continue
        
                except Exception as error:
                    self.error(f"Unknown error: <light-yellow>{error} ::: {traceback.format_exc()}</light-yellow>")
        

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        self.error(f"{tg_client.name} | Invalid Session")
