from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    # тут можете менять под себя
    API_ID: int = 12345
    API_HASH: str = 'API_HASH Text'

    PAINT_REWARD_MAX: int = 7
    ENERGY_LIMIT_MAX: int = 7
    RE_CHARGE_SPEED_MAX: int = 11

    USE_PROXY_FROM_FILE: bool = False

    ENABLE_AUTO_TASKS: bool = True
    ENABLE_AUTO_DRAW: bool = True
    ENABLE_JOIN_TG_CHANNELS: bool = True
    ENABLE_CLAIM_REWARD: bool = True
    ENABLE_AUTO_UPGRADE: bool = True

    IMAGE_LINK: str = 'https://app.notpx.app/assets/dungeon_4-B7Qp6JGr.png'
    X_OFFSET: int = 372
    Y_OFFSET: int = 372
    DOWNLOAD_METHOD_2: bool = False
    DOWNLOAD_FROM_FILE: bool = False
    LOCAL_LINK_TO_FILE: str = 'file.png'

# настройки ниже лучше не трогать

    USE_RANDOM_DELAY_IN_RUN: bool = True
    RANDOM_DELAY_IN_RUN: list[int] = [5, 30]

    SLEEP_TIME_IN_MINUTES: list[int] = [30, 60]

    ENABLE_AUTO_JOIN_TO_SQUAD_CHANNEL: bool = True
    ENABLE_AUTO_JOIN_TO_SQUAD: bool = True
    SQUAD_SLUG: str = 'rm_sud0'
    USE_REF: bool = False
    REF_ID: str = 'f5064842218_t_s717211'

    IN_USE_SESSIONS_PATH: str = 'bot/config/used_sessions.txt'

    DISABLE_IN_NIGHT: bool = True
    NIGHT_TIME: list[int] = [23, 5]

    DRAW_RANDOM_X_DIAPOSON: list[int] = [456, 567]
    DRAW_RANDOM_Y_DIAPOSON: list[int] = [120, 231]
    DRAW_RANDOM_COLORS: list[str] = ["#000000"]

    ENABLE_EXPERIMENTAL_X3_MODE: bool = False
    ENABLE_DRAW_ART: bool = False
    DRAW_ART_COORDS: list[dict] = [
        {
            'color': "#6A5CFF",
            'x': { 'type': 'diaposon', 'value': [995, 999] },
            'y': { 'type': 'random', 'value': [995, 999] }
        }
    ]

    ENABLE_SSL: bool = False

    BOOSTS_BLACK_LIST: list[str] = ['invite3frens', 'INVITE_FRIENDS', 'TON_TRANSACTION', 'BOOST_CHANNEL', 'ACTIVITY_CHALLENGE', 'CONNECT_WALLET']
    TASKS_TODO_LIST: list[str] = ["x:notcoin", "x:notpixel", "paint20pixels", "leagueBonusSilver", "leagueBonusGold", "leagueBonusPlatinum", "boinkTask", "makePixelAvatar", "jettonTask", "channel:notpixel_channel", "channel:notcoin", "joinSquad"]


settings = Settings()


