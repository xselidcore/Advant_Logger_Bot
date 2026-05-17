import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.types import FSInputFile, BusinessConnection, Message, BotCommand
from aiogram.utils.i18n import gettext as _, I18n, SimpleI18nMiddleware

from filters.ContentTypeFilter import ContentTypeFilter
from handlers.deleting import message_delete_route
from handlers.edit import message_edit_route
from handlers.receive import message_receive_route
from middlewares.user_check import UsersMiddleware
from repo import Repo
from repo.modules.users import UserData
from utils.config import config
from utils.encryptor import get_text_hash

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
)

dp = Dispatcher()
i18n = I18n(path="locales", default_locale="en", domain="messages")

dp.update.middleware(SimpleI18nMiddleware(i18n=i18n))
dp.update.middleware(UsersMiddleware())

dp.include_routers(message_receive_route, message_edit_route, message_delete_route)

repo = Repo(
    username=config.DATABASE.username,
    password=config.DATABASE.password,
    ip=config.DATABASE.ip,
    port=config.DATABASE.port,
    db=config.DATABASE.db,
)

dp["repo"] = repo


@dp.business_connection()
async def connection_handler(bc: BusinessConnection, bot: Bot) -> None:
    connection_id = get_text_hash(bc.id)
    user = repo.users.get(bc.user.id)

    if not bc.is_enabled:
        logger.info("User %s (%d) disconnected — clearing data", bc.user.full_name, bc.user.id)
        repo.messages.delete_by_cid(connection_id=connection_id)
        repo.users.delete(user=user)
        await bot.send_message(chat_id=bc.user.id,
                               text=_("⚠ All your data was cleared because of disconnecting"))
        return

    logger.info("Business connection from %s (%d), connection_id=%s", bc.user.full_name, bc.user.id, connection_id)

    if user is not None:
        if user.connection_id != connection_id:
            logger.info("User %d reconnected with new connection_id, clearing old messages", bc.user.id)
            user.connection_id = connection_id
            repo.save()
            repo.messages.delete_by_cid(connection_id=connection_id)

    s = repo.users.add(UserData(id=bc.user.id,
                                connection_id=get_text_hash(bc.id),
                                language=bc.user.language_code))
    if s:
        logger.info("New user registered: %s (%d)", bc.user.full_name, bc.user.id)
        await bot.send_message(
            chat_id=config.BOT.admin_id,
            text=f"<tg-emoji emoji-id=\"5343584360182349563\">➕</tg-emoji> Новый пользователь\n"
                f"<b><a href='tg://user?id={bc.user.id}'>{bc.user.full_name}</a></b>\n"
                f"ID: <code>{bc.user.id}</code>"
        )

        text = _("<tg-emoji emoji-id=\"5343584360182349563\">➕</tg-emoji> <b>Бот успешно подключён!</b>\n"
            "Привет, <b><a href='tg://user?id={user_id}'>{name}</a></b>!\n\n"
            "Теперь я буду отслеживать изменения и удаления сообщений в твоих переписках.").format(
        name=bc.user.full_name,
        user_id=bc.user.id)
        await bot.send_photo(chat_id=bc.user.id,
                             caption=text,
                             photo=FSInputFile("images/bot_connected.png"))
                             


@dp.message(ContentTypeFilter(ContentType.TEXT,))
async def start_handler(msg: Message, bot: Bot) -> None:
    logger.info("/start from %s (%d)", msg.from_user.full_name, msg.from_user.id)

    bot_username = dp["bot_info"].username

    text = _("Привет, <b><a href='tg://user?id={user_id}'>{name}</a></b>!"
             "\nЯ помогу тебе отслеживать изменения и удаления сообщений в личных переписках!"
             "\n\n<b>Как подключить:</b>"
             "\n1. Откройте <b>Настройки</b> Telegram"
             "\n2. → <b>Telegram Business</b>"
             "\n3. → <b>Чат-боты</b>"
             "\n4. Введите <code>@{bot_username}</code> и подключите"
             "\n\n<i>⚠️ Требуется Telegram Premium</i>").format(
        name=msg.from_user.full_name,
        user_id=msg.from_user.id,
        bot_username=bot_username)

    await bot.send_photo(chat_id=msg.from_user.id,
                         caption=text,
                         photo=FSInputFile("images/welcome.png"))


async def main() -> None:
    bot = Bot(
        token=config.BOT.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )

    bot_info = await bot.get_me()
    dp["bot_info"] = bot_info
    logger.info("Bot started: @%s (id=%d)", bot_info.username, bot_info.id)

    await bot.set_my_commands(
        commands=[BotCommand(command="start", description="Short information about bot capabilities")],
        language_code="en"
    )
    await bot.set_my_commands(
        commands=[BotCommand(command="start", description="Краткая информация о возможностях бота")],
        language_code="ru"
    )
    logger.info("Commands set, starting polling...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
