import asyncio
import logging
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import CommandObject, Command
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.utils.token import TokenValidationError
from aiogram.utils.markdown import html_decoration
from sqlalchemy.future import select
from data.bot import BotToken

from config import *
from data.db_session import global_init, create_session
from polling_manager import PollingManager

logger = logging.getLogger(__name__)


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


async def add_bot(
    message: types.Message,
    command: CommandObject,
    dp_for_new_bot: Dispatcher,
    polling_manager: PollingManager,
):
    if command.args:
        try:
            bot = Bot(command.args)

            if bot.id in polling_manager.polling_tasks:
                await message.answer("Bot with this id already running")
                return

            async with create_session() as sess:
                bot_token = BotToken()
                bot_token.token = command.args
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
            bot_user = await bot.get_me()
            await message.answer(f"New bot started: @{bot_user.username}")
        except (TokenValidationError, TelegramUnauthorizedError) as err:
            await message.answer(html_decoration.quote(f"{type(err).__name__}: {str(err)}"))
    else:
        await message.answer("Please provide token")


async def echo(message: types.Message):
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

    if bot_tokens:
        bots = [Bot(token) for token in bot_tokens]
        dp = Dispatcher()

        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        dp.message.register(echo)

        await dp.start_polling(*bots, dp_for_new_bot=dp, polling_manager=polling_manager)
    bot = Bot(TOKEN)
    dp = Dispatcher()
    dp.message.register(add_bot, Command(commands="add_bot"))
    await dp.start_polling(bot, dp_for_new_bot=dp, polling_manager=polling_manager)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Exit")