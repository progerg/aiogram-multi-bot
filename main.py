import asyncio
import logging
from pprint import pprint
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import CommandObject, Command, Text
from aiogram.dispatcher.fsm.context import FSMContext
from aiogram.dispatcher.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramUnauthorizedError

from aiogram.utils.token import TokenValidationError
from aiogram.utils.markdown import html_decoration
from sqlalchemy.future import select
from data.bot import BotToken

from config import *
from data.db_session import global_init, create_session
from polling_manager import PollingManager

logger = logging.getLogger(__name__)


class Main(StatesGroup):
    menu = State()
    add = State()


async def on_bot_startup(bot: Bot):
    bot_info = await bot.me()
    print(f"{bot_info.first_name} startup")


async def on_bot_shutdown(bot: Bot):
    bot_info = await bot.me()
    print(f"{bot_info.first_name} shutdown")


async def on_startup(bots: List[Bot]):
    for bot in bots:
        await on_bot_startup(bot)


async def on_shutdown(bots: List[Bot]):
    for bot in bots:
        await on_bot_shutdown(bot)


async def start(message: types.Message, state: FSMContext):
    await state.set_state(Main.menu)
    markup = [
        [types.KeyboardButton(text="Создать бота")],
        [types.KeyboardButton(text="Мои боты")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=markup, one_time_keyboard=True)
    await message.answer(text='Привет', reply_markup=keyboard)


async def add_bot_button(message: types.Message, state: FSMContext):
    await state.set_state(Main.add)
    await message.answer("Введите BOT_TOKEN")


async def add_bot(
    message: types.Message,
    dp_for_new_bot: Dispatcher,
    polling_manager: PollingManager,
    state: FSMContext
):
    try:
        bot = Bot(message.text)
        bot_user = await bot.get_me()

        if bot.id in polling_manager.polling_tasks:
            await message.answer("Бот уже запущен")
            return

        async with create_session() as sess:
            bot_token = BotToken()
            bot_token.bot_id = bot.id
            bot_token.token = message.text
            bot_token.count = 0
            bot_token.username = bot_user.username
            sess.add(bot_token)
            await sess.commit()

        polling_manager.start_bot_polling(
            dp=dp_for_new_bot,
            bot=bot,
            on_bot_startup=on_bot_startup(bot),
            on_bot_shutdown=on_bot_shutdown(bot),
            polling_manager=polling_manager,
            dp_for_new_bot=dp_for_new_bot,
        )
        markup = [
            [types.KeyboardButton(text="Создать бота")],
            [types.KeyboardButton(text="Мои боты")]
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=markup, one_time_keyboard=True)
        await message.answer(f"Новый бот стартанул: @{bot_user.username}", reply_markup=keyboard)
        await state.set_state(Main.menu)
    except (TokenValidationError, TelegramUnauthorizedError) as err:
        await message.answer(html_decoration.quote(f"{type(err).__name__}: {str(err)}"))


async def my_bots(message: types.Message):
    async with create_session() as sess:
        result = await sess.execute(select(BotToken))
        bot_tokens = result.scalars().all()
    for bot in bot_tokens:
        await message.answer(f"{bot.bot_id} - {bot.username} - {bot.token}")


async def echo(message: types.Message, polling_manager: PollingManager, dp_for_new_bot: Dispatcher):
    await message.answer(message.text)


async def main():
    await global_init(user=user, password=password, dbname=dbname, port=port, host=host)
    async with create_session() as sess:
        result = await sess.execute(select(BotToken.token))
        bot_tokens = result.scalars().all()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    polling_manager = PollingManager()
    bot = Bot(TOKEN)

    dp = Dispatcher()
    dp.message.register(start, Command(commands="start"))
    dp.message.register(add_bot_button, Text(text="Создать бота"), Main.menu)
    dp.message.register(my_bots, Text(text="Мои боты"), Main.menu)
    dp.message.register(add_bot, Main.add)

    dp_new = Dispatcher()

    dp_new.startup.register(on_startup)
    dp_new.shutdown.register(on_shutdown)

    dp_new.message.register(echo)
    if bot_tokens:

        bots = [Bot(token) for token in bot_tokens]
        for i in bots:
            # await dp_new.start_polling(*bots, dp_for_new_bot=dp_new, polling_manager=polling_manager)
            polling_manager.start_bot_polling(
                dp=dp_new,
                bot=i,
                on_bot_startup=on_bot_startup(i),
                on_bot_shutdown=on_bot_shutdown(i),
                polling_manager=polling_manager,
                dp_for_new_bot=dp_new,
            )

    await dp.start_polling(bot, dp_for_new_bot=dp_new, polling_manager=polling_manager)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Exit")