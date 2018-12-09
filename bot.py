import asyncio
import logging
import traceback

import requests
from discord import Client
from vk_api import VkApi, ApiError, Captcha
from vk_api.bot_longpoll import VkBotEventType
from vk_api.longpoll import VkEventType

from handler.handler import VkHandler, DiscordHandler
from settings import Settings
from utils import utils
from utils.data import MyVkBotLongPoll, MyVkLongPoll, VkMessage, DSMessage, StoppableThread


class Bot:
    __client = Client()
    __ds_handler = None
    __loop = None
    __logger = None

    def __init__(self, settings):
        try:
            self.settings = settings

            self.loop = asyncio.get_event_loop()

            self.vk_t = StoppableThread(target=self.processor)
            self.ds_t = StoppableThread(target=self.ds_processor)

            # Logger
            self.logger = None
            self.logger_file = None
            self.init_logger()

            if len(settings.auth) == 0:
                self.logger.error('Not set any auth method!')
                exit(-1)

            # VK
            self.session = None
            self.api = None
            self.vk_auth_type = ''
            self.vk_auth()

            # Discord
            self.ds_client = Bot.__client
            self.ds_token = ''
            self.ds_auth()

            self.vk_handler = VkHandler(self.api, self)
            self.ds_handler = DiscordHandler(self.ds_client, self)
            Bot.__ds_handler = self.ds_handler
            Bot.__loop = self.loop
            Bot.__logger = self.logger

            self.run()
        except(KeyboardInterrupt, SystemExit):
            self.loop.run_until_complete(self.stop())

    def init_logger(self):
        formatter = logging.Formatter(fmt='%(filename)s [%(asctime)s] %(levelname)s: %(message)s',
                                      datefmt='%d-%m-%Y %H:%M:%S')
        level = logging.DEBUG if self.settings.debug else logging.INFO
        self.logger = logging.Logger('bot', level=level)

        file_handler = logging.FileHandler('log.txt')
        file_handler.setLevel(level=level)
        file_handler.setFormatter(formatter)
        self.logger_file = file_handler

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level=level)
        stream_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)

    @staticmethod
    def auth_handler():
        return input('Enter two-auth code:\n'), True

    def captcha_handler(self, c: Captcha):
        with open('captcha.jpg', 'wb') as handle:
            response = requests.get(c.url, stream=True)
            for block in response.iter_content(1024):
                if not block:
                    break
                handle.write(block)
        return input('Enter code from captcha.jpg:\n')

    def vk_auth(self):
        for auth in self.settings.auth:
            if auth[0] == 'vk_group':
                if len(auth) == 1:
                    self.logger.critical('Not set token!')
                    exit(-1)
                try:
                    self.session = VkApi(api_version='5.89', token=auth[1],
                                         app_id=self.settings.app_id, auth_handler=self.auth_handler,
                                         captcha_handler=self.captcha_handler)
                    self.api = self.session.get_api()
                    group = self.api.groups.getById()[0]
                    self.logger.info(f'Auth as {group["name"]} (https://vk.com/public{group["id"]})')
                    self.vk_auth_type = 'vk_group'
                except ApiError:
                    self.logger.critical('Wrong token! Shutting down...')
                    exit(-1)

            elif auth[0] == 'vk_user' and len(auth) == 2:
                try:
                    self.session = VkApi(api_version='5.89', token=auth[1],
                                         app_id=self.settings.app_id, auth_handler=self.auth_handler,
                                         captcha_handler=self.captcha_handler, scope=self.settings.scope)
                    self.api = self.session.get_api()
                    user = self.api.users.get()[0]
                    self.logger.info(f'Auth as {user["first_name"]} {user["last_name"]} '
                                     f'(https://vk.com/id{user["id"]})')
                    self.vk_auth_type = 'vk_user'
                except ApiError:
                    self.logger.critical('Wrong token! Shutting down...')

            elif auth[0] == 'vk_user' and len(auth) >= 3:
                try:
                    self.session = VkApi(api_version='5.89', login=auth[1], password=auth[2],
                                         app_id=self.settings.app_id, auth_handler=self.auth_handler,
                                         captcha_handler=self.captcha_handler, scope=self.settings.scope)
                    self.session.auth()
                    self.api = self.session.get_api()
                    user = self.api.users.get()[0]
                    self.logger.info(f'Auth as {user["first_name"]} {user["last_name"]} '
                                     f'(https://vk.com/id{user["id"]})')
                    self.vk_auth_type = 'vk_user'
                except ApiError:
                    self.logger.critical('Wrong login and/or password! Shutting down...')

    def ds_auth(self):
        for a in self.settings.auth:
            if a[0] == 'ds_bot':
                if len(a) <= 1:
                    self.logger.critical('Token for Discord bot not set!')
                    exit(-1)
                self.ds_token = a[1]

    @staticmethod
    @__client.event
    async def on_message(message):
        await asyncio.ensure_future(Bot.__ds_handler.process(DSMessage(message, Bot.__client)), loop=Bot.__loop)

    @staticmethod
    @__client.event
    async def on_ready():
        Bot.__logger.info(f'Logged in as {Bot.__client.user.name} ({Bot.__client.user.id})')

    def run(self):
        self.logger.info('Started to process messages')

        try:
            self.vk_t.start()
            self.ds_t.start()
        except asyncio.CancelledError:
            pass

    def ds_processor(self):
        Bot.__client.run(self.ds_token)

    def processor(self):
        longpoll = MyVkBotLongPoll(self.session, utils.get_self_id(self.api)) if self.vk_auth_type == 'vk_group'\
            else MyVkLongPoll(self.session)
        try:
            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self.process_vk_msg(VkMessage(self.session, event.raw))
                elif event.type == VkEventType.MESSAGE_NEW:
                    self.process_vk_msg(VkMessage(self.session, utils.user_raw_to_data(event.raw)))

        except:
            self.logger.error(traceback.format_exc())

    def process_vk_msg(self, msg):
        asyncio.ensure_future(self.vk_handler.process(msg), loop=self.loop)

    async def stop(self):
        try:
            self.loop.stop()
            self.ds_t.stop()
            self.vk_t.stop()
            self.logger.removeHandler(self.logger_file)
            self.logger_file.close()
            self.logger.info('Stopped to process messages')
        except:
            print(traceback.format_exc())


if __name__ == '__main__':
    bot = Bot(Settings)