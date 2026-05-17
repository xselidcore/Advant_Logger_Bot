import typing

from aiogram import Router, Bot
from aiogram.enums import ContentType
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import FSInputFile, BusinessConnection, Message, BotCommand
from pathlib import Path

from filters.ContentTypeFilter import ContentTypeFilter
from repo import Repo
from repo.modules.messages import MessageData
from repo.modules.users import UserData
from utils.encryptor import get_text_hash, TextEncryptor

message_edit_route = Router()

SIGNAL = Path(__file__).parent.parent / "images" / "signal.png"

async def get_data(repo: Repo, business_connection_id,
                      from_user_id, message_id) -> typing.Optional[tuple[UserData, MessageData]]:
    user = repo.users.get_by_connection(get_text_hash(business_connection_id))

    if user is None:
        return

    if user.id == from_user_id:
        return

    connection_id = get_text_hash(business_connection_id)

    message = repo.messages.get(message_id=message_id, connection_id=connection_id)

    if message is None:
        return

    return user, message


# Text edit handler
@message_edit_route.edited_business_message(ContentTypeFilter(ContentType.TEXT, ))
async def text_edit(bm: Message, bot: Bot, repo: Repo) -> None:
    data = await get_data(repo, bm.business_connection_id, bm.from_user.id, bm.message_id)
    if data is None: return

    message = data[1]
    user = data[0]

    user_link = ""
    if bm.chat.has_private_forwards:
        user_link = f"tg://user?id={bm.chat.id}"
    elif bm.chat.username is not None:
        user_link = "https://t.me/" + bm.chat.username

    text = _("<tg-emoji emoji-id=\"5301173701323028420\">✏️</tg-emoji> <b>Edit  ·  <a href='{user_link}'>{name}</a></b>"
             "\n\n<i>Was</i>"
             "<blockquote expandable>{old_msg}</blockquote>"
             "<i>Now</i>"
             "<blockquote expandable>{new_msg}</blockquote>",
             locale=user.language).format(user_link=user_link,
                                          name=bm.chat.full_name,
                                          new_msg=bm.html_text,
                                          old_msg=TextEncryptor(key=bm.business_connection_id).decrypt(
                                              message.message))

    message.message = TextEncryptor(key=bm.business_connection_id).encrypt(bm.html_text)
    repo.save()
    await bot.send_message(chat_id=user.id, text=text)


# Video, Photo, Animation, Voice, Audio caption edit handler
@message_edit_route.edited_business_message(ContentTypeFilter(ContentType.PHOTO,
                                                               ContentType.VIDEO,
                                                               ContentType.ANIMATION,
                                                               ContentType.VOICE,
                                                               ContentType.AUDIO,
                                                               ContentType.DOCUMENT))
async def media_edit(bm: Message, bot: Bot, repo: Repo) -> None:
    data = await get_data(repo, bm.business_connection_id, bm.from_user.id, bm.message_id)
    if data is None: return

    message = data[1]
    user = data[0]

    user_link = ""
    if bm.chat.has_private_forwards:
        user_link = f"tg://user?id={bm.chat.id}"
    elif bm.chat.username is not None:
        user_link = "https://t.me/" + bm.chat.username

    text = _("<tg-emoji emoji-id=\"5301173701323028420\">✏️</tg-emoji> <b>Edit  ·  <a href='{user_link}'>{name}</a></b>"
             "\n\n<i>Was</i>"
             "<blockquote expandable>{old_msg}</blockquote>"
             "<i>Now</i>"
             "<blockquote expandable>{new_msg}</blockquote>",
             locale=user.language).format(user_link=user_link,
                                          name=bm.chat.full_name,
                                          new_msg=bm.html_text,
                                          old_msg=TextEncryptor(key=bm.business_connection_id).decrypt(
                                              message.message) if message.message is not None else "")
    await bot.send_photo(chat_id=user.id, photo=FSInputFile(SIGNAL), caption=text)

    message.message = TextEncryptor(key=bm.business_connection_id).encrypt(bm.html_text)
    repo.save()

    if bm.content_type == ContentType.PHOTO:
        media = bm.photo[-1].file_id
    else:
        media = bm.model_dump()[bm.content_type]['file_id']

    if bm.content_type not in [ContentType.ANIMATION]:
        media_group = MediaGroupBuilder(caption=text)
        media_group.add(type=message.media_type if message.media_type not in [ContentType.VOICE] else ContentType.AUDIO,
                        media=TextEncryptor(key=bm.business_connection_id).decrypt(message.media))

        if media != TextEncryptor(key=bm.business_connection_id).decrypt(message.media):
            media_group.add(type=bm.content_type if bm.content_type not in [ContentType.VOICE] else ContentType.AUDIO,
                            media=media)

        message.media = TextEncryptor(key=bm.business_connection_id).encrypt(media)
        repo.save()

        await bot.send_media_group(chat_id=user.id, media=media_group.build())
    else:
        if bm.content_type == ContentType.ANIMATION:
            message.media = TextEncryptor(key=bm.business_connection_id).encrypt(media)
            repo.save()

            await bot.send_animation(chat_id=user.id, animation=media, caption=text)




@message_edit_route.edited_business_message()
async def not_handled(msg: Message):
    print(msg.content_type)