from pyrogram import Client
import random
from bot.config import settings
from bot.core.agents import generate_random_user_agent
from bot.utils import logger
from bot.utils.file_manager import save_to_json

android_device = random.choice([
    'SM-G960F', 'SM-G973F', 'SM-G980F', 'SM-G960U', 'SM-G973U', 'SM-G980U',
    'SM-A505F', 'SM-A515F', 'SM-A525F', 'SM-N975F', 'SM-N986B', 'SM-N981B',
    'SM-F711B', 'SM-F916B', 'SM-G781B', 'SM-G998B', 'SM-G991B', 'SM-G996B',
    'SM-G990E', 'SM-G990B2', 'SM-G990U', 'SM-G990B', 'SM-G990', 'SM-G990',
    'Pixel 2', 'Pixel 2 XL', 'Pixel 3', 'Pixel 3 XL', 'Pixel 4', 'Pixel 4 XL',
    'Pixel 4a', 'Pixel 5', 'Pixel 5a', 'Pixel 6', 'Pixel 6 Pro', 'Pixel 6 XL',
    'Pixel 6a', 'Pixel 7', 'Pixel 7 Pro', 'IN2010', 'IN2023',
    'LE2117', 'LE2123', 'OnePlus Nord', 'IV2201', 'NE2215', 'CPH2423',
    'NE2210', 'Mi 9', 'Mi 10', 'Mi 11', 'Mi 12', 'Redmi Note 8',
    'Redmi Note 8 Pro', 'Redmi Note 9', 'Redmi Note 9 Pro', 'Redmi Note 10',
    'Redmi Note 10 Pro', 'Redmi Note 11', 'Redmi Note 11 Pro', 'Redmi Note 12',
    'Redmi Note 12 Pro', 'VOG-AL00', 'ANA-AL00', 'TAS-AL00',
    'OCE-AN10', 'J9150', 'J9210', 'LM-G820', 'L-51A', 'Nokia 8.3',
    'Nokia 9 PureView', 'POCO F5', 'POCO F5 Pro', 'POCO M3', 'POCO M3 Pro'
])

async def register_sessions() -> None:
    API_ID = settings.API_ID
    API_HASH = settings.API_HASH

    if not API_ID or not API_HASH:
        raise ValueError("API_ID и API_HASH не найдены ")

    session_name = input('\nВведи название сессии, желательно на английском (нажми Enter чтобы выйти): ')

    if not session_name:
        return None

    raw_proxy = input("Введи прокси в формате type://user:pass:ip:port (нажми Enter чтобы продолжить без прокси): ")
    session = await get_tg_client(session_name=session_name, proxy=raw_proxy)
    async with session:
        user_data = await session.get_me()

    user_agent = generate_random_user_agent(device_type='android', browser_type='chrome')
    save_to_json(f'sessions/accounts.json',
                 dict_={
                    "session_name": session_name,
                    "user_agent": user_agent,
                    "proxy": raw_proxy if raw_proxy else None
                 })
    logger.success(f'Сессия успешно создана @{user_data.username} | {user_data.first_name} {user_data.last_name}')


async def get_tg_client(session_name: str, proxy: str | None) -> Client:
    if not session_name:
        raise FileNotFoundError(f"Не найдена сессия {session_name}")

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError("API_ID и API_HASH не найдены ")

    proxy_dict = {
        "scheme": proxy.split(":")[0],
        "username": proxy.split(":")[1].split("//")[1],
        "password": proxy.split(":")[2],
        "hostname": proxy.split(":")[3],
        "port": int(proxy.split(":")[4])
    } if proxy else None

    tg_client = Client(
        name=session_name,
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        app_version='1.6.7',
        device_model=android_device,
        workdir="sessions/",
        plugins=dict(root="bot/plugins"),
        proxy=proxy_dict
    )

    return tg_client