import os
import re
import secrets
import string
import traceback

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
CommandHandler,
MessageHandler,
CallbackQueryHandler,
TypeHandler,
ContextTypes,
filters,
)

import database


# =========================================================
# تنظیمات اصلی
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

BOT_USERNAME = "FilmBinDownloadBot"

# کانال اصلی فیلم‌بین
FILM_CHANNEL = "@FilmBinTV15FilmBinMovie"

# کانال آرشیو
ARCHIVE_CHANNEL = "@P_sh_Archive"

# عضویت اجباری
REQUIRED_CHATS = [
    ("@Istgah_Khande118", "کانال اول"),
    ("@ZarabanHeart_Music", "کانال دوم"),
    ("@FilmBin_vs_ZarabanMusic", "گروه"),
]

# حذف خودکار پیام خوش‌آمدگویی
AUTO_DELETE_SECONDS = int(
    os.getenv("AUTO_DELETE_SECONDS", "120")
)


# =========================================================
# مراحل ثبت فیلم
# =========================================================

WAIT_TITLE = 1
WAIT_ORIGINAL = 2
WAIT_CATEGORY = 3
WAIT_IMDB = 4
WAIT_COUNTRY = 5
WAIT_DIRECTOR = 6
WAIT_STARS = 7
WAIT_SYNOPSIS = 8
WAIT_SUBTITLE = 9

WAIT_360 = 10
WAIT_480 = 11
WAIT_720 = 12
WAIT_1080 = 13

WAIT_CONFIRM = 14


# =========================================================
# توابع کمکی
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def generate_code():
    chars = string.ascii_letters + string.digits

    return "film_" + "".join(
        secrets.choice(chars)
        for _ in range(8)
    )


def normalize(text):

    if not text:
        return ""

    return (
        text
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .strip()
    )


# =========================================================
# بررسی واقعی عضویت کاربر
# =========================================================

async def get_missing_memberships(
    bot,
    user_id,
):

    missing = []

    for chat, name in REQUIRED_CHATS:

        try:

            member = await bot.get_chat_member(
                chat,
                user_id,
            )

            # کاربر از کانال/گروه خارج شده یا بن شده
            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.BANNED,
            ):

                missing.append(name)

            # برای وضعیت Restricted
            elif (
                member.status == ChatMemberStatus.RESTRICTED
                and hasattr(member, "is_member")
                and not member.is_member
            ):

                missing.append(name)

        except Exception as error:

            print(
                f"MEMBERSHIP CHECK ERROR "
                f"{chat}: {error}"
            )

            missing.append(name)

    return missing


# =========================================================
# حذف خودکار
# =========================================================

async def delete_later(context):

    job = context.job

    try:

        await context.bot.delete_message(
            chat_id=job.chat_id,
            message_id=job.data,
        )

    except Exception:

        pass


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    database.add_user(user.id)

    # -----------------------------------------------------
    # /start بدون لینک
    # -----------------------------------------------------

    if not context.args:

        await send_welcome(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # دریافت کد فیلم
    # -----------------------------------------------------

    start_code = context.args[0].strip()

    print(
        "START PARAMETER:",
        start_code,
    )

    quality = None

    movie_code = start_code

    parts = start_code.split("_")

    # -----------------------------------------------------
    # تشخیص کیفیت
    # -----------------------------------------------------

    if len(parts) >= 3:

        possible_quality = parts[-1].lower()

        if possible_quality in (
            "360p",
            "480p",
            "720p",
            "1080p",
        ):

            quality = possible_quality

            movie_code = "_".join(
                parts[:-1]
            )

    print(
        "MOVIE CODE:",
        movie_code,
    )

    print(
        "QUALITY:",
        quality,
    )

    # -----------------------------------------------------
    # پیدا کردن فیلم
    # -----------------------------------------------------

    movie = database.get_movie_by_code(
        movie_code
    )

    print(
        "MOVIE FOUND:",
        bool(movie),
    )

    if not movie:

        await update.message.reply_text(
            "❌ لینک فیلم معتبر نیست یا فیلم حذف شده است."
        )

        return

    # -----------------------------------------------------
    # بررسی عضویت واقعی در همین لحظه
    # -----------------------------------------------------

    missing = await get_missing_memberships(
        context.bot,
        user.id,
    )

    # -----------------------------------------------------
    # اگر عضو همه است → مستقیم فیلم
    # -----------------------------------------------------

    if not missing:

        print(
            "USER IS MEMBER OF ALL REQUIRED CHATS:",
            user.id,
        )

        await send_movie_to_user(
            user.id,
            movie["id"],
            quality,
            context,
        )

        return

    # -----------------------------------------------------
    # اگر عضو نیست → نمایش صفحه عضویت
    # -----------------------------------------------------

    print(
        "MISSING MEMBERSHIPS:",
        missing,
    )

    await show_membership(
        update,
        context,
        movie["id"],
        quality,
    )


# =========================================================
# خوش‌آمدگویی
# =========================================================

async def send_welcome(
    update,
    context,
):

    user = update.effective_user

    text = (
        "🎬 به ربات فیلم‌بین خوش آمدید!\n\n"
        "🔎 از این ربات می‌توانید فیلم موردنظر خود را "
        "جستجو و کیفیت موردنظر را دریافت کنید.\n\n"
        "🔐 برای دریافت فیلم باید ابتدا در کانال‌ها "
        "و گروه مشخص‌شده عضو شوید."
    )

    buttons = [
        [
            InlineKeyboardButton(
                "🔎 جستجوی فیلم",
                callback_data="search",
            )
        ],
        [
            InlineKeyboardButton(
                "🎬 جدیدترین فیلم‌ها",
                callback_data="list",
            )
        ],
        [
            InlineKeyboardButton(
                "⭐ علاقه‌مندی‌ها",
                callback_data="favorites",
            )
        ],
        [
            InlineKeyboardButton(
                "🔔 تنظیم اعلان‌ها",
                callback_data="notifications",
            )
        ], 
        [
            InlineKeyboardButton(
                "📖 راهنمای دریافت",
                callback_data="guide",
            )
        ],
    ]

    if is_admin(user.id):

        buttons.append(
            [
                InlineKeyboardButton(
                    "⚙️ پنل مدیریت",
                    callback_data="admin",
                )
            ]
        )

    msg = await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            buttons
        )
    )

    context.job_queue.run_once(
        delete_later,
        AUTO_DELETE_SECONDS,
        data=msg.message_id,
        chat_id=msg.chat_id,
        name=f"welcome_{msg.message_id}",
    )



# =========================================================
# عضویت اجباری
# =========================================================

async def show_membership(
    update,
    context,
    movie_id,
    quality=None,
):

    buttons = []

    for chat, name in REQUIRED_CHATS:

        buttons.append(
            [
                InlineKeyboardButton(
                    f"📢 عضویت در {name}",
                    url=(
                        f"https://t.me/"
                        f"{chat.lstrip('@')}"
                    ),
                )
            ]
        )

    quality_value = quality or "all"

    buttons.append(
        [
            InlineKeyboardButton(
                "✅ بررسی عضویت",
                callback_data=(
                    f"check:"
                    f"{movie_id}:"
                    f"{quality_value}"
                ),
            )
        ]
    )

    text = (
        "🔐 برای دریافت فیلم، ابتدا در موارد زیر عضو شوید:\n\n"
        "1️⃣ کانال اول\n"
        "2️⃣ کانال دوم\n"
        "3️⃣ گروه فیلم‌بین\n\n"
        "بعد از عضویت روی «✅ بررسی عضویت» بزنید."
    )

    if update.callback_query:

        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )


# =========================================================
# بررسی عضویت
# =========================================================

async def check_membership(
    update,
    context,
):

    query = update.callback_query

    _, movie_id, quality = query.data.split(
        ":",
        2,
    )

    movie_id = int(movie_id)

    user_id = query.from_user.id

    # -----------------------------------------------------
    # بررسی واقعی عضویت
    # -----------------------------------------------------

    missing = await get_missing_memberships(
        context.bot,
        user_id,
    )

    # -----------------------------------------------------
    # هنوز عضو کامل نیست
    # -----------------------------------------------------

    if missing:

        await query.answer(
            "❌ هنوز عضویت شما در همه موارد کامل نشده است.",
            show_alert=True,
        )

        return

    # -----------------------------------------------------
    # عضویت کامل است
    # -----------------------------------------------------

    await query.answer(
        "✅ عضویت شما تأیید شد."
    )

    try:

        await query.message.delete()

    except Exception:

        pass

    if quality == "all":

        quality = None

    # -----------------------------------------------------
    # ارسال فیلم
    # -----------------------------------------------------

    await send_movie_to_user(
        user_id,
        movie_id,
        quality,
        context,
    )

# =========================================================
# راهنمای دریافت فیلم
# =========================================================

async def guide_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    text = (
        "📖 راهنمای دریافت فیلم\n\n"
        "1️⃣ ابتدا فیلم موردنظر را از بخش "
        "«🔎 جستجوی فیلم» پیدا کنید.\n\n"
        "2️⃣ روی نام فیلم بزنید.\n\n"
        "3️⃣ اگر عضو کانال‌ها و گروه‌های موردنیاز نیستید، "
        "ابتدا عضو شوید.\n\n"
        "4️⃣ بعد از عضویت روی «✅ بررسی عضویت» بزنید.\n\n"
        "5️⃣ پس از تأیید عضویت، کیفیت موردنظر خود را انتخاب کنید.\n\n"
        "6️⃣ فایل فیلم برای شما ارسال می‌شود. 🎬📥"
    )

    await query.message.reply_text(
        text
    )
    
# =========================================================
# ارسال فیلم
# =========================================================

async def send_movie_to_user(
    user_id,
    movie_id,
    quality,
    context,
):

    movie = database.get_movie(
        movie_id
    )

    if not movie:

        await context.bot.send_message(
            user_id,
            "❌ فیلم پیدا نشد.",
        )

        return

    if movie["status"] != "published":

        await context.bot.send_message(
            user_id,
            "❌ این فیلم هنوز منتشر نشده است.",
        )

        return

    files = database.get_movie_files(
        movie_id
    )

    selected = None

    for file in files:

        if quality and file["quality"] == quality:

            selected = file

            break
            
    # -----------------------------------------------------
    # اگر کیفیت مشخص نشده
    # -----------------------------------------------------
    
    if not quality:

        buttons = []

        poster = movie["poster_file_id"]

        if poster:

            await context.bot.send_photo(
                user_id,
                poster,
                caption=(
                    f"🎬 {movie['title']}\n"
                    f"🎭 ژانر: {movie['category'] or 'نامشخص'}\n\n"
                    "📥 کیفیت موردنظر را انتخاب کنید:"
                ),
            )

        for file in files:

            link = (
                f"https://t.me/{BOT_USERNAME}"
                f"?start="
                f"{movie['code']}_{file['quality']}"
            )

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"📥 {file['quality']}",
                        url=link,
                    )
                ]
            )

        # -----------------------------------------------------
        # علاقه‌مندی
        # -----------------------------------------------------

        if database.is_favorite(
            user_id,
            movie_id,
        ):

            favorite_text = "⭐ حذف از علاقه‌مندی‌ها"

        else:

            favorite_text = "⭐ افزودن به علاقه‌مندی‌ها"

        buttons.append(
            [
                InlineKeyboardButton(
                    favorite_text,
                    callback_data=f"favorite:{movie_id}",
                )
            ]
        )

        await context.bot.send_message(
            user_id,
            "📥 کیفیت موردنظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        return
        
    # -----------------------------------------------------
    # کیفیت موجود نیست
    # -----------------------------------------------------

    if not selected:

        await context.bot.send_message(
            user_id,
            "❌ این کیفیت برای فیلم موجود نیست.",
        )

        return

    # -----------------------------------------------------
    # ارسال فایل
    # -----------------------------------------------------

    try:

        if selected["file_type"] == "video":

            await context.bot.send_video(
                user_id,
                selected["file_id"],
                caption=(
                    f"🎬 {movie['title']}\n"
                    f"📥 کیفیت: {quality}"
                ),
            )

        else:

            await context.bot.send_document(
                user_id,
                selected["file_id"],
                caption=(
                    f"🎬 {movie['title']}\n"
                    f"📥 کیفیت: {quality}"
                ),
            )

        database.record_download(
            user_id,
            movie_id,
            quality,
        )

    except Exception as error:

        print(
            "SEND MOVIE ERROR:",
            error,
        )

        await context.bot.send_message(
            user_id,
            "❌ ارسال فایل انجام نشد.",
        )


# =========================================================
# پنل مدیریت
# =========================================================

def admin_menu_markup():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎬 افزودن فیلم",
                    callback_data="add",
                )
            ],
            [
                InlineKeyboardButton(
                    "📝 ثبت فیلم موجود",
                    callback_data="existing",
                )
            ],
            [
                InlineKeyboardButton(
                    "📚 لیست فیلم‌ها",
                    callback_data="list_admin",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔎 جستجوی فیلم",
                    callback_data="search_admin",
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف فیلم",
                    callback_data="delete_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 آمار",
                    callback_data="stats",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ بستن پنل",
                    callback_data="close",
                )
            ],
        ]
    )


async def admin_panel(
    update,
    context,
):

    if not is_admin(
        update.effective_user.id
    ):

        if update.callback_query:

            await update.callback_query.answer(
                "⛔ دسترسی ندارید.",
                show_alert=True,
            )

        return

    text = (
        "🎬 پنل مدیریت فیلم‌بین\n\n"
        "یک گزینه را انتخاب کنید:"
    )

    if update.callback_query:

        await update.callback_query.message.edit_text(
            text,
            reply_markup=admin_menu_markup(),
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=admin_menu_markup(),
        )


# =========================================================
# دکمه‌های پنل
# =========================================================

async def admin_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if not is_admin(user_id):

        await query.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True,
        )

        return

    data = query.data

    # -----------------------------------------------------
    # پنل
    # -----------------------------------------------------

    if data == "admin":

        await admin_panel(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # افزودن فیلم
    # -----------------------------------------------------

    if data in (
        "add",
        "existing",
    ):

        context.user_data.clear()

        context.user_data["mode"] = data

        context.user_data["state"] = WAIT_TITLE

        if data == "existing":

            await query.message.reply_text(
                "📝 ثبت فیلم موجود از آرشیو\n\n"
                "ابتدا نام فیلم را بفرست.\n"
                "بعداً فایل‌های موجود در "
                "@P_sh_Archive را می‌توانی به ربات بفرستی."
            )

        else:

            await query.message.reply_text(
                "🎬 نام فیلم را بفرست:"
            )

        return

    # -----------------------------------------------------
    # لیست فیلم‌های کاربر
    # -----------------------------------------------------

    if data == "list":

        rows = database.get_latest_movies(30)

        if not rows:

            await query.message.edit_text(
                "📭 هنوز فیلم منتشرشده‌ای وجود ندارد.",
                reply_markup=admin_menu_markup(),
            )

            return

        buttons = []

        for movie in rows[:30]:

            buttons.append(
                [
                    InlineKeyboardButton(
                        movie["title"],
                        callback_data=(
                            f"movie:{movie['id']}"
                        ),
                    )
                ]
            )

        await query.message.edit_text(
            "📚 فیلم‌های منتشرشده:",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        return

    # -----------------------------------------------------
    # لیست مدیریت
    # -----------------------------------------------------

    if data == "list_admin":

        rows = database.get_all_movies()

        if not rows:

            await query.message.edit_text(
                "📭 هنوز فیلمی ثبت نشده.",
                reply_markup=admin_menu_markup(),
            )

            return

        text = "📚 لیست فیلم‌ها:\n\n"

        for movie in rows[:30]:

            text += (
                f"#{movie['id']} — "
                f"{movie['title']} — "
                f"{movie['status']}\n"
            )

        await query.message.edit_text(
            text,
            reply_markup=admin_menu_markup(),
        )

        return

    # -----------------------------------------------------
    # آمار
    # -----------------------------------------------------

    if data == "stats":

        stats = database.get_stats()

        text = (
            "📊 آمار فیلم‌بین\n\n"
            f"👤 کاربران: {stats['users']}\n"
            f"🎬 کل فیلم‌ها: {stats['movies']}\n"
            f"📢 منتشرشده: {stats['published']}\n"
            f"📁 فایل‌ها: {stats['files']}\n"
            f"📥 دانلودها: {stats['downloads']}"
        )

        await query.message.edit_text(
            text,
            reply_markup=admin_menu_markup(),
        )

        return

    # -----------------------------------------------------
    # جستجو
    # -----------------------------------------------------

    if data in (
        "search",
        "search_admin",
    ):

        context.user_data["search_admin"] = (
            data == "search_admin"
        )

        context.user_data["search_user"] = (
            data == "search"
        )

        await query.message.reply_text(
            "🔎 نام فیلم را بفرست:"
        )

        return

    # -----------------------------------------------------
    # حذف
    # -----------------------------------------------------

    if data == "delete_menu":

        context.user_data[
            "await_delete_id"
        ] = True

        await query.message.reply_text(
            "🗑 شناسه فیلم را بفرست.\n\n"
            "مثلاً:\n"
            "12"
        )

        return

    # -----------------------------------------------------
    # بستن
    # -----------------------------------------------------

    if data == "close":

        try:

            await query.message.delete()

        except Exception:

            pass

        return


# =========================================================
# متن‌های دریافتی
# =========================================================

async def text_router(
    update,
    context,
):

    user = update.effective_user

    database.add_user(user.id)

    state = context.user_data.get(
        "state"
    )

    # -----------------------------------------------------
    # ثبت فیلم
    # -----------------------------------------------------

    if state in (
        WAIT_TITLE,
        WAIT_ORIGINAL,
        WAIT_CATEGORY,
        WAIT_IMDB,
        WAIT_COUNTRY,
        WAIT_DIRECTOR,
        WAIT_STARS,
        WAIT_SYNOPSIS,
        WAIT_SUBTITLE,
        WAIT_360,
        WAIT_480,
        WAIT_720,
        WAIT_1080,
        "poster",
        "trailer",
    ):

        if not is_admin(user.id):

            return

        return await registration_text(
            update,
            context,
        )

    # -----------------------------------------------------
    # حذف فیلم
    # -----------------------------------------------------

    if (
        context.user_data.get(
            "await_delete_id"
        )
        and is_admin(user.id)
    ):

        context.user_data.pop(
            "await_delete_id",
            None,
        )

        try:

            movie_id = int(
                update.message.text.strip()
            )

        except ValueError:

            await update.message.reply_text(
                "❌ شناسه نامعتبر است."
            )

            return

        movie = database.get_movie(
            movie_id
        )

        if not movie:

            await update.message.reply_text(
                "❌ فیلم پیدا نشد."
            )

            return

        buttons = [
            [
                InlineKeyboardButton(
                    "🗑 بله، حذف شود",
                    callback_data=(
                        f"confirmdel:{movie_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="admin",
                )
            ],
        ]

        await update.message.reply_text(
            f"⚠️ آیا فیلم زیر حذف شود؟\n\n"
            f"🎬 {movie['title']}",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        return

    # -----------------------------------------------------
    # جستجو
    # -----------------------------------------------------

    if (
        context.user_data.get(
            "search_admin"
        )
        or context.user_data.get(
            "search_user"
        )
    ):

        admin_search = context.user_data.pop(
            "search_admin",
            False,
        )

        context.user_data.pop(
            "search_user",
            None,
        )

        rows = database.search_movies(
            normalize(
                update.message.text
            )
        )

        if not rows:

            await update.message.reply_text(
                "❌ فیلمی پیدا نشد."
            )

            return

        buttons = []

        for movie in rows:

            buttons.append(
                [
                    InlineKeyboardButton(
                        movie["title"],
                        callback_data=(
                            f"movie:{movie['id']}"
                        ),
                    )
                ]
            )

        await update.message.reply_text(
            "🔎 نتایج جستجو:",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        return


# =========================================================
# مراحل متنی ثبت فیلم
# =========================================================

async def registration_text(
    update,
    context,
):

    text = update.message.text.strip()

    state = context.user_data.get(
        "state"
    )

    # -----------------------------------------------------
    # نام فیلم
    # -----------------------------------------------------

    if state == WAIT_TITLE:

        context.user_data["title"] = text

        context.user_data["state"] = WAIT_ORIGINAL

        await update.message.reply_text(
            "📝 نام اصلی / انگلیسی فیلم را بفرست.\n"
            "اگر نداری: /skip"
        )

        return

    # -----------------------------------------------------
    # نام اصلی
    # -----------------------------------------------------

    if state == WAIT_ORIGINAL:

        context.user_data[
            "original_title"
        ] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_CATEGORY

        await update.message.reply_text(
            "🎭 ژانر فیلم را بفرست.\n"
            "مثلاً: #اکشن #درام\n\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # ژانر
    # -----------------------------------------------------

    if state == WAIT_CATEGORY:

        context.user_data["category"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_IMDB

        await update.message.reply_text(
            "⭐ امتیاز IMDb را بفرست.\n"
            "مثلاً: 7.5\n\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # IMDb
    # -----------------------------------------------------

    if state == WAIT_IMDB:

        context.user_data["imdb"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_COUNTRY

        await update.message.reply_text(
            "🌍 کشور سازنده را بفرست.\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # کشور
    # -----------------------------------------------------

    if state == WAIT_COUNTRY:

        context.user_data["country"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_DIRECTOR

        await update.message.reply_text(
            "🎬 نام کارگردان را بفرست.\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # کارگردان
    # -----------------------------------------------------

    if state == WAIT_DIRECTOR:

        context.user_data["director"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_STARS

        await update.message.reply_text(
            "⭐ نام بازیگران را بفرست.\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # بازیگران
    # -----------------------------------------------------

    if state == WAIT_STARS:

        context.user_data["stars"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_SYNOPSIS

        await update.message.reply_text(
            "📖 خلاصه داستان را بفرست.\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # خلاصه
    # -----------------------------------------------------

    if state == WAIT_SYNOPSIS:

        context.user_data["synopsis"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = WAIT_SUBTITLE

        await update.message.reply_text(
            "📝 وضعیت فیلم را بنویس.\n"
            "مثلاً:\n"
            "#زیرنویس_چسبیده_فارسی\n\n"
            "یا /skip"
        )

        return

    # -----------------------------------------------------
    # زیرنویس
    # -----------------------------------------------------

    if state == WAIT_SUBTITLE:

        context.user_data["subtitle"] = (
            ""
            if text.lower() == "/skip"
            else text
        )

        context.user_data["state"] = "poster"

        await update.message.reply_text(
            "🖼 حالا پوستر فیلم را به صورت عکس بفرست:"
        )

        return

    # -----------------------------------------------------
    # کیفیت
    # -----------------------------------------------------

    if state in (
        WAIT_360,
        WAIT_480,
        WAIT_720,
        WAIT_1080,
    ):

        if text.lower() == "/skip":

            quality_map = {
                WAIT_360: "360p",
                WAIT_480: "480p",
                WAIT_720: "720p",
                WAIT_1080: "1080p",
            }

            quality = quality_map[state]

            context.user_data.setdefault(
                "qualities",
                {},
            )[quality] = None

            await next_quality(
                update,
                context,
                quality,
            )

        else:

            await update.message.reply_text(
                "❌ فایل کیفیت را بفرست یا /skip."
            )

        return

    # -----------------------------------------------------
    # تریلر
    # -----------------------------------------------------

    if state == "trailer":

        if text.lower() == "/skip":

            context.user_data[
                "trailer_file_id"
            ] = None

            context.user_data[
                "trailer_type"
            ] = None

            context.user_data["state"] = WAIT_360

            await update.message.reply_text(
                "📥 فایل کیفیت 360p را بفرست یا /skip:"
            )

        else:

            await update.message.reply_text(
                "🎬 تریلر را به صورت ویدیو بفرست "
                "یا /skip."
            )

        return


# =========================================================
# فایل‌های دریافتی
# =========================================================

async def moviecodes_command(update, context):

    user = update.effective_user

    if user is None:
        return

    if not is_admin(user.id):
        await update.message.reply_text(
            "⛔ این دستور فقط برای مدیر است."
        )
        return

    conn = database.get_db()

    rows = conn.execute("""
        SELECT id, code, title, status
        FROM movies
        ORDER BY id
    """).fetchall()

    conn.close()

    if not rows:
        await update.message.reply_text(
            "📭 هیچ فیلمی در دیتابیس نیست."
        )
        return

    text = "🎬 کد فیلم‌ها:\n\n"

    for row in rows:
        text += (
            f"#{row['id']}\n"
            f"🎬 عنوان: {row['title']}\n"
            f"🔑 کد: {row['code']}\n"
            f"📌 وضعیت: {row['status']}\n\n"
        )

    await update.message.reply_text(text)


async def debug_channel_update(update, context):

    if update.channel_post:

        print("\n" + "=" * 60)
        print("CHANNEL POST RECEIVED")
        print("=" * 60)

        print(
            "CHANNEL ID:",
            update.channel_post.chat.id,
        )

        print(
            "CHANNEL USERNAME:",
            update.channel_post.chat.username,
        )

        print(
            "MESSAGE ID:",
            update.channel_post.message_id,
        )

        print("=" * 60 + "\n")



async def archive_media_handler(update, context):

    message = update.channel_post

    if message is None:
        return

    # فقط کانال آرشیو
    if not message.chat:
        return

    if message.chat.username != "P_sh_Archive":
        return

    print("\n" + "=" * 60)
    print("ARCHIVE FILE RECEIVED")
    print("=" * 60)

    print(
        "CHANNEL:",
        message.chat.username,
    )

    print(
        "MESSAGE ID:",
        message.message_id,
    )

    # -----------------------------------------------------
    # تشخیص فایل
    # -----------------------------------------------------

    file_id = None
    file_type = None

    if message.video:

        file_id = message.video.file_id
        file_type = "video"

        print("TYPE: VIDEO")

    elif message.document:

        file_id = message.document.file_id
        file_type = "document"

        print("TYPE: DOCUMENT")

    else:

        print(
            "❌ این پیام فایل ویدیویی یا document نیست."
        )

        print("=" * 60 + "\n")

        return

    print(
        "FILE ID:",
        file_id,
    )

    # -----------------------------------------------------
    # خواندن کپشن
    # -----------------------------------------------------

    caption = (
        message.caption.strip()
        if message.caption
        else ""
    )

    print(
        "CAPTION:",
        caption,
    )

    if not caption:

        print(
            "❌ کپشن ندارد."
        )

        await context.bot.send_message(
            ADMIN_IDS.pop()
            if False
            else next(iter(ADMIN_IDS)),
            (
                "⚠️ فایل جدیدی در آرشیو دریافت شد، "
                "اما کپشن ندارد.\n\n"
                "فرمت کپشن باید مثلاً این باشد:\n"
                "ABC123 720p"
            ),
        )

        print("=" * 60 + "\n")

        return

    # -----------------------------------------------------
    # استخراج کد فیلم و کیفیت
    # -----------------------------------------------------

    parts = caption.replace("_", " ").split()

    quality = None

    for item in parts:

        if item.lower() in (
            "360p",
            "480p",
            "720p",
            "1080p",
        ):

            quality = item.lower()

            break

    if not quality:

        print(
            "❌ کیفیت از کپشن پیدا نشد."
        )

        await context.bot.send_message(
            next(iter(ADMIN_IDS)),
            (
                "⚠️ فایل آرشیو دریافت شد، "
                "اما کیفیت مشخص نیست.\n\n"
                "فرمت صحیح کپشن:\n"
                "ABC123 720p"
            ),
        )

        print("=" * 60 + "\n")

        return

    # -----------------------------------------------------
    # حذف کیفیت از کپشن و استخراج کد فیلم
    # -----------------------------------------------------

    movie_code = caption.strip()

    for q in (
        "360p",
        "480p",
        "720p",
        "1080p",
    ):

        movie_code = movie_code.replace(
            q,
            "",
        ).replace(
            q.upper(),
            "",
        )

    movie_code = movie_code.strip()

    print(
        "MOVIE CODE:",
        movie_code,
    )

    print(
        "QUALITY:",
        quality,
    )

    # -----------------------------------------------------
    # پیدا کردن فیلم
    # -----------------------------------------------------

    movie = database.get_movie_by_code(
        movie_code
    )

    if not movie:

        print(
            "❌ MOVIE NOT FOUND:",
            movie_code,
        )

        await context.bot.send_message(
            next(iter(ADMIN_IDS)),
            (
                "❌ فایل آرشیو دریافت شد، "
                "اما فیلم پیدا نشد.\n\n"
                f"🎬 کد فیلم: {movie_code}\n"
                f"📥 کیفیت: {quality}\n\n"
                "ابتدا فیلم را در ربات ثبت کنید."
            ),
        )

        print("=" * 60 + "\n")

        return

    movie_id = movie["id"]

    print(
        "MOVIE ID:",
        movie_id,
    )

    print(
        "MOVIE TITLE:",
        movie["title"],
    )

    # -----------------------------------------------------
    # ذخیره فایل در movie_files
    # -----------------------------------------------------

    try:

        database.add_movie_file(
            movie_id,
            quality,
            file_id,
            file_type,
        )

        print(
            "✅ FILE SAVED TO DATABASE"
        )

    except Exception as error:

        print(
            "❌ DATABASE ERROR:",
            repr(error),
        )

        await context.bot.send_message(
            next(iter(ADMIN_IDS)),
            (
                "❌ ذخیره فایل آرشیو در دیتابیس "
                "انجام نشد.\n\n"
                f"🎬 فیلم: {movie['title']}\n"
                f"📥 کیفیت: {quality}\n"
                f"❌ خطا: {error}"
            ),
        )

        print("=" * 60 + "\n")

        return

    # -----------------------------------------------------
    # پیام موفقیت
    # -----------------------------------------------------

    print(
        "✅ ARCHIVE FILE REGISTERED"
    )

    print(
        "MOVIE:",
        movie["title"],
    )

    print(
        "QUALITY:",
        quality,
    )

    print("=" * 60 + "\n")

    await context.bot.send_message(
        next(iter(ADMIN_IDS)),
        (
            "✅ فایل آرشیو ثبت شد!\n\n"
            f"🎬 فیلم: {movie['title']}\n"
            f"📥 کیفیت: {quality}\n"
            f"📁 نوع فایل: {file_type}"
        ),
    )

async def media_router(update, context):

    user = update.effective_user

    # پیام‌های کانال کاربر ندارند
    if user is None:
        return

    if not is_admin(user.id):
        return

    state = context.user_data.get(
        "state"
    )

    # -----------------------------------------------------
    # پوستر
    # -----------------------------------------------------

    if state == "poster":

        if update.message.photo:

            context.user_data[
                "poster_file_id"
            ] = update.message.photo[-1].file_id

            context.user_data["state"] = "trailer"

            await update.message.reply_text(
                "🎬 تریلر را بفرست.\n"
                "اگر تریلر نداری: /skip"
            )

        else:

            await update.message.reply_text(
                "❌ لطفاً پوستر را به صورت عکس بفرست."
            )

        return

    # -----------------------------------------------------
    # تریلر
    # -----------------------------------------------------

    if state == "trailer":

        if update.message.video:

            context.user_data[
                "trailer_file_id"
            ] = update.message.video.file_id

            context.user_data[
                "trailer_type"
            ] = "video"

        elif update.message.document:

            context.user_data[
                "trailer_file_id"
            ] = update.message.document.file_id

            context.user_data[
                "trailer_type"
            ] = "document"

        else:

            await update.message.reply_text(
                "❌ تریلر باید ویدیو یا فایل باشد."
            )

            return

        context.user_data["state"] = WAIT_360

        await update.message.reply_text(
            "📥 فایل کیفیت 360p را بفرست یا /skip:"
        )

        return

    # -----------------------------------------------------
    # کیفیت‌ها
    # -----------------------------------------------------

    quality_map = {
        WAIT_360: "360p",
        WAIT_480: "480p",
        WAIT_720: "720p",
        WAIT_1080: "1080p",
    }

    if state in quality_map:

        quality = quality_map[state]

        if update.message.video:

            file_id = update.message.video.file_id

            file_type = "video"

        elif update.message.document:

            file_id = update.message.document.file_id

            file_type = "document"

        else:

            await update.message.reply_text(
                "❌ فایل باید ویدیو یا document باشد."
            )

            return

        context.user_data.setdefault(
            "qualities",
            {},
        )[quality] = (
            file_id,
            file_type,
        )

        await next_quality(
            update,
            context,
            quality,
        )


# =========================================================
# مرحله بعد کیفیت
# =========================================================

async def next_quality(
    update,
    context,
    current_quality,
):

    next_state = {
        "360p": WAIT_480,
        "480p": WAIT_720,
        "720p": WAIT_1080,
        "1080p": WAIT_CONFIRM,
    }[current_quality]

    context.user_data["state"] = next_state

    if current_quality != "1080p":

        next_quality_name = {
            WAIT_480: "480p",
            WAIT_720: "720p",
            WAIT_1080: "1080p",
        }[next_state]

        await update.message.reply_text(
            f"📥 فایل کیفیت {next_quality_name} را "
            f"بفرست یا /skip:"
        )

    else:

        await show_preview(
            update,
            context,
        )


# =========================================================
# پیش‌نمایش
# =========================================================

async def show_preview(
    update,
    context,
):

    data = context.user_data

    qualities = [
        quality
        for quality, value
        in data.get(
            "qualities",
            {},
        ).items()
        if value
    ]

    if not qualities:

        await update.message.reply_text(
            "❌ حداقل یک کیفیت باید ثبت شود."
        )

        return

    text = (
        f"🎬 {data.get('title', '')}\n\n"
        f"{data.get('original_title', '')}\n\n"
        f"⭐ IMDb: {data.get('imdb') or '—'}\n\n"
        f"🎭 ژانر: {data.get('category') or '—'}\n\n"
        f"🌍 کشور: {data.get('country') or '—'}\n\n"
        f"🎬 کارگردان:\n"
        f"{data.get('director') or '—'}\n\n"
        f"⭐ بازیگران:\n"
        f"{data.get('stars') or '—'}\n\n"
        f"📝 وضعیت:\n"
        f"{data.get('subtitle') or '—'}\n\n"
        f"📖 خلاصه:\n"
        f"{data.get('synopsis') or '—'}\n\n"
        f"📥 کیفیت‌ها:\n"
        f"{', '.join(qualities)}"
    )

    buttons = [
        [
            InlineKeyboardButton(
                "✅ ثبت و ارسال برای تأیید",
                callback_data="register",
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ شروع دوباره",
                callback_data="restart",
            ),
            InlineKeyboardButton(
                "❌ لغو",
                callback_data="cancel",
            ),
        ],
    ]

    await update.message.reply_text(
        "🔎 پیش‌نمایش فیلم:\n\n" + text,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =========================================================
# ثبت فیلم
# =========================================================

async def registration_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    if not is_admin(
        query.from_user.id
    ):

        return

    # -----------------------------------------------------
    # لغو
    # -----------------------------------------------------

    if query.data == "cancel":

        context.user_data.clear()

        await query.message.edit_text(
            "❌ ثبت فیلم لغو شد.",
            reply_markup=admin_menu_markup(),
        )

        return

    # -----------------------------------------------------
    # شروع دوباره
    # -----------------------------------------------------

    if query.data == "restart":

        context.user_data.clear()

        context.user_data["state"] = WAIT_TITLE

        await query.message.edit_text(
            "🎬 نام فیلم را بفرست:"
        )

        return

    # -----------------------------------------------------
    # ثبت
    # -----------------------------------------------------

    if query.data == "register":

        data = context.user_data

        movie_code = generate_code()

        movie_id = database.add_movie(
            {
                "code": movie_code,
                "title": data.get("title"),
                "original_title": data.get(
                    "original_title"
                ),
                "category": data.get("category"),
                "imdb": data.get("imdb"),
                "country": data.get("country"),
                "director": data.get("director"),
                "stars": data.get("stars"),
                "synopsis": data.get("synopsis"),
                "subtitle": data.get("subtitle"),
                "poster_file_id": data.get(
                    "poster_file_id"
                ),
                "trailer_file_id": data.get(
                    "trailer_file_id"
                ),
                "trailer_type": data.get(
                    "trailer_type"
                ),
            }
        )

        for quality, item in data.get(
            "qualities",
            {},
        ).items():

            if item:

                database.add_movie_file(
                    movie_id,
                    quality,
                    item[0],
                    item[1],
                )

        buttons = [
            [
                InlineKeyboardButton(
                    "✅ انتشار",
                    callback_data=(
                        f"publish:{movie_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 حذف",
                    callback_data=(
                        f"confirmdel:{movie_id}"
                    ),
                )
            ],
        ]

        link = (
            f"https://t.me/{BOT_USERNAME}"
            f"?start={movie_code}"
        )

        await query.message.edit_text(
            "✅ فیلم ثبت شد!\n\n"
            f"🎬 {data.get('title')}\n"
            f"🔑 کد: {movie_code}\n\n"
            f"🔗 لینک:\n{link}\n\n"
            "⏳ وضعیت: در انتظار تأیید انتشار",
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        context.user_data.clear()


# =========================================================
# انتشار در کانال
# =========================================================

async def publish_movie(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    if not is_admin(
        query.from_user.id
    ):

        return

    movie_id = int(
        query.data.split(":")[1]
    )

    movie = database.get_movie(
        movie_id
    )

    if not movie:

        return

    files = database.get_movie_files(
        movie_id
    )

    if not files:

        await query.message.reply_text(
            "❌ هیچ فایل کیفیتی برای این فیلم ثبت نشده."
        )

        return

    qualities = [
        file["quality"]
        for file in files
    ]

    text = (
        f"🎬 {movie['title']}\n\n"
        f"{movie['original_title'] or ''}\n\n"
        f"{movie['subtitle'] or '#فیلم'}\n\n"
        f"⭐ امتیاز IMDb : "
        f"{movie['imdb'] or '—'}\n\n"
        f"🎭 ژانر: "
        f"{movie['category'] or '—'}\n\n"
        f"🌍 محصول کشور: "
        f"{movie['country'] or '—'}\n\n"
        f"🎬 کارگردان:\n"
        f"{movie['director'] or '—'}\n\n"
        f"⭐ ستارگان:\n"
        f"{movie['stars'] or '—'}\n\n"
        f"📖 خلاصه داستان:\n"
        f"{movie['synopsis'] or '—'}\n\n"
        "🎬 فیلم‌بین"
    )

    message_ids = []

    try:

        # -------------------------------------------------
        # پوستر
        # -------------------------------------------------

        if movie["poster_file_id"]:

            caption = text[:1024]

            poster_message = (
                await context.bot.send_photo(
                    FILM_CHANNEL,
                    movie["poster_file_id"],
                    caption=caption,
                )
            )

        else:

            poster_message = (
                await context.bot.send_message(
                    FILM_CHANNEL,
                    text[:4096],
                )
            )

        message_ids.append(
            poster_message.message_id
        )

        # -------------------------------------------------
        # متن اضافی
        # -------------------------------------------------

        if (
            movie["poster_file_id"]
            and len(text) > 1024
        ):

            extra_message = (
                await context.bot.send_message(
                    FILM_CHANNEL,
                    text[1024:],
                )
            )

            message_ids.append(
                extra_message.message_id
            )

        # -------------------------------------------------
        # تریلر
        # -------------------------------------------------

        if movie["trailer_file_id"]:

            if movie["trailer_type"] == "video":

                trailer_message = (
                    await context.bot.send_video(
                        FILM_CHANNEL,
                        movie["trailer_file_id"],
                        caption="🎬 تریلر",
                    )
                )

            else:

                trailer_message = (
                    await context.bot.send_document(
                        FILM_CHANNEL,
                        movie["trailer_file_id"],
                        caption="🎬 تریلر",
                    )
                )

            message_ids.append(
                trailer_message.message_id
            )

        # -------------------------------------------------
        # دکمه‌های کیفیت
        # -------------------------------------------------

        buttons = []

        row = []

        for quality in qualities:

            link = (
                f"https://t.me/{BOT_USERNAME}"
                f"?start="
                f"{movie['code']}_{quality}"
            )

            row.append(
                InlineKeyboardButton(
                    quality,
                    url=link,
                )
            )

            if len(row) == 2:

                buttons.append(row)

                row = []

        if row:

            buttons.append(row)

        quality_message = (
            await context.bot.send_message(
                FILM_CHANNEL,
                (
                    "📥 برای دریافت کیفیت موردنظر، "
                    "گزینه موردنظر را انتخاب کنید:"
                ),
                reply_markup=InlineKeyboardMarkup(
                    buttons
                ),
            )
        )

        message_ids.append(
            quality_message.message_id
        )

        # -------------------------------------------------
        # ذخیره پیام‌های کانال
        # -------------------------------------------------

        database.save_channel_message_ids(
            movie_id,
            message_ids,
        )

        # -------------------------------------------------
        # تغییر وضعیت
        # -------------------------------------------------

        database.set_movie_status(
            movie_id,
            "published",
        )

        await query.message.edit_text(
            "✅ فیلم با موفقیت در کانال فیلم‌بین منتشر شد.",
            reply_markup=admin_menu_markup(),
        )

    except Exception as error:

        print(
            "PUBLISH ERROR:",
            error,
        )

        await query.message.reply_text(
            "❌ انتشار انجام نشد.\n\n"
            "مطمئن شو ربات در کانال فیلم‌بین "
            "ادمین باشد و اجازه ارسال پست داشته باشد."
        )


# =========================================================
# نمایش فیلم از نتایج جستجو
# =========================================================

async def movie_view(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    movie_id = int(
        query.data.split(":")[1]
    )

    movie = database.get_movie(
        movie_id
    )

    if not movie:

        await query.message.reply_text(
            "❌ فیلم پیدا نشد."
        )

        return

    user_id = query.from_user.id

    # -----------------------------------------------------
    # عضویت واقعی را بررسی کن
    # -----------------------------------------------------

    missing = await get_missing_memberships(
        context.bot,
        user_id,
    )

    # اگر عضو همه است
    if not missing:

        await send_movie_to_user(
            user_id,
            movie_id,
            None,
            context,
        )

        return

    # اگر عضو نیست
    await show_membership(
        update,
        context,
        movie_id,
    )


# =========================================================
# علاقه‌مندی‌ها
# =========================================================

async def favorite_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    movie_id = int(
        query.data.split(":")[1]
    )

    movie = database.get_movie(
        movie_id
    )

    if not movie:

        await query.answer(
            "❌ فیلم پیدا نشد.",
            show_alert=True,
        )

        return

    if database.is_favorite(
        user_id,
        movie_id,
    ):

        database.remove_favorite(
            user_id,
            movie_id,
        )

        await query.answer(
            "💔 از علاقه‌مندی‌ها حذف شد."
        )

    else:

        database.add_favorite(
            user_id,
            movie_id,
        )

        await query.answer(
            "⭐ به علاقه‌مندی‌ها اضافه شد."
        )

    await send_movie_to_user(
        user_id,
        movie_id,
        None,
        context,
    )

# =========================================================
# نمایش علاقه‌مندی‌ها
# =========================================================

async def favorites_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    movies = database.get_user_favorites(
        user_id
    )

    if not movies:

        await query.message.edit_text(
            "⭐ هنوز هیچ فیلمی را به علاقه‌مندی‌ها اضافه نکرده‌اید."
        )

        return

    buttons = []

    for movie in movies:

        buttons.append(
            [
                InlineKeyboardButton(
                    f"🎬 {movie['title']}",
                    callback_data=f"movie:{movie['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="back_home",
            )
        ]
    )

    await query.message.edit_text(
        "⭐ فیلم‌های موردعلاقه شما:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )
    
# =========================================================
# بازگشت به منوی اصلی
# =========================================================

async def back_home_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    text = (
        "🎬 به ربات فیلم‌بین خوش آمدید!\n\n"
        "🔎 از این ربات می‌توانید فیلم موردنظر خود را "
        "جستجو و کیفیت موردنظر را دریافت کنید.\n\n"
        "🔐 برای دریافت فیلم باید ابتدا در کانال‌ها "
        "و گروه مشخص‌شده عضو شوید."
    )

    buttons = [
        [
            InlineKeyboardButton(
                "🔎 جستجوی فیلم",
                callback_data="search",
            )
        ],
        [
            InlineKeyboardButton(
                "🎬 جدیدترین فیلم‌ها",
                callback_data="list",
            )
        ],
        [
            InlineKeyboardButton(
                "⭐ علاقه‌مندی‌ها",
                callback_data="favorites",
            )
        ],
        [
            InlineKeyboardButton(
                "📖 راهنمای دریافت",
                callback_data="guide",
            )
        ],
    ]

    if is_admin(user.id):

        buttons.append(
            [
                InlineKeyboardButton(
                    "⚙️ پنل مدیریت",
                    callback_data="admin",
                )
            ]
        )

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )
    
# =========================================================
# تنظیم اعلان‌ها
# =========================================================

async def notifications_button(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    enabled = database.get_notifications_status(
        user_id
    )

    if enabled:

        text = (
            "🔔 اعلان‌های فیلم جدید فعال است.\n\n"
            "هر زمان فیلم جدیدی منتشر شود، "
            "به شما اطلاع داده خواهد شد."
        )

    else:

        text = (
            "🔕 اعلان‌های فیلم جدید خاموش است.\n\n"
            "در صورت خاموش بودن، اعلان فیلم‌های جدید "
            "برای شما ارسال نمی‌شود."
        )

    buttons = [
        [
            InlineKeyboardButton(
                "🔔 روشن کردن اعلان‌ها",
                callback_data="notify_on",
            )
        ],
        [
            InlineKeyboardButton(
                "🔕 خاموش کردن اعلان‌ها",
                callback_data="notify_off",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="back_home",
            )
        ],
    ]

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )
    
# =========================================================
# تغییر وضعیت اعلان‌ها
# =========================================================

async def notification_toggle(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if query.data == "notify_on":

        database.set_notifications_status(
            user_id,
            True,
        )

        text = (
            "🔔 اعلان‌های فیلم جدید فعال شد.\n\n"
            "از این به بعد هنگام انتشار فیلم جدید "
            "به شما اطلاع داده می‌شود."
        )

    else:

        database.set_notifications_status(
            user_id,
            False,
        )

        text = (
            "🔕 اعلان‌های فیلم جدید خاموش شد.\n\n"
            "دیگر اعلان فیلم‌های جدید برای شما ارسال نمی‌شود."
        )

    buttons = [
        [
            InlineKeyboardButton(
                "🔔 روشن کردن اعلان‌ها",
                callback_data="notify_on",
            )
        ],
        [
            InlineKeyboardButton(
                "🔕 خاموش کردن اعلان‌ها",
                callback_data="notify_off",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="back_home",
            )
        ],
    ]

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

# =========================================================
# حذف فیلم
# =========================================================

async def confirm_delete(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    if not is_admin(
        query.from_user.id
    ):

        return

    movie_id = int(
        query.data.split(":")[1]
    )

    movie = database.get_movie(
        movie_id
    )

    if not movie:

        return

    message_ids = database.get_channel_message_ids(
        movie_id
    )

    for message_id in message_ids:

        try:

            await context.bot.delete_message(
                FILM_CHANNEL,
                int(message_id),
            )

        except Exception:

            pass

    database.delete_movie(
        movie_id
    )

    await query.message.edit_text(
        "✅ فیلم و رکوردهای مربوط به آن حذف شد.",
        reply_markup=admin_menu_markup(),
    )


# =========================================================
# /id
# =========================================================

async def id_command(
    update,
    context,
):

    await update.message.reply_text(
        "🆔 شناسه عددی شما:\n\n"
        f"`{update.effective_user.id}`",
        parse_mode="Markdown",
    )


# =========================================================
# /skip
# =========================================================

async def skip_command(
    update,
    context,
):

    if not is_admin(
        update.effective_user.id
    ):

        return

    state = context.user_data.get(
        "state"
    )

    # -----------------------------------------------------
    # تریلر
    # -----------------------------------------------------

    if state == "trailer":

        context.user_data[
            "trailer_file_id"
        ] = None

        context.user_data[
            "trailer_type"
        ] = None

        context.user_data[
            "state"
        ] = WAIT_360

        await update.message.reply_text(
            "📥 فایل کیفیت 360p را بفرست یا /skip:"
        )

        return

    # -----------------------------------------------------
    # کیفیت‌ها
    # -----------------------------------------------------

    quality_map = {
        WAIT_360: "360p",
        WAIT_480: "480p",
        WAIT_720: "720p",
        WAIT_1080: "1080p",
    }

    if state in quality_map:

        quality = quality_map[state]

        context.user_data.setdefault(
            "qualities",
            {},
        )[quality] = None

        await next_quality(
            update,
            context,
            quality,
        )

        return

    # -----------------------------------------------------
    # فیلدهای اختیاری
    # -----------------------------------------------------

    optional_fields = {
        WAIT_ORIGINAL: "original_title",
        WAIT_CATEGORY: "category",
        WAIT_IMDB: "imdb",
        WAIT_COUNTRY: "country",
        WAIT_DIRECTOR: "director",
        WAIT_STARS: "stars",
        WAIT_SYNOPSIS: "synopsis",
        WAIT_SUBTITLE: "subtitle",
    }

    if state in optional_fields:

        field = optional_fields[state]

        context.user_data[field] = ""

        next_state = {
            WAIT_ORIGINAL: WAIT_CATEGORY,
            WAIT_CATEGORY: WAIT_IMDB,
            WAIT_IMDB: WAIT_COUNTRY,
            WAIT_COUNTRY: WAIT_DIRECTOR,
            WAIT_DIRECTOR: WAIT_STARS,
            WAIT_STARS: WAIT_SYNOPSIS,
            WAIT_SYNOPSIS: WAIT_SUBTITLE,
            WAIT_SUBTITLE: "poster",
        }[state]

        context.user_data["state"] = next_state

        prompts = {
            WAIT_ORIGINAL:
                "🎭 ژانر را بفرست یا /skip",

            WAIT_CATEGORY:
                "⭐ امتیاز IMDb را بفرست یا /skip",

            WAIT_IMDB:
                "🌍 کشور سازنده را بفرست یا /skip",

            WAIT_COUNTRY:
                "🎬 کارگردان را بفرست یا /skip",

            WAIT_DIRECTOR:
                "⭐ بازیگران را بفرست یا /skip",

            WAIT_STARS:
                "📖 خلاصه داستان را بفرست یا /skip",

            WAIT_SYNOPSIS:
                "📝 وضعیت زیرنویس/دوبله را بفرست یا /skip",

            WAIT_SUBTITLE:
                "🖼 حالا پوستر فیلم را به صورت عکس بفرست:",
        }

        await update.message.reply_text(
            prompts[state]
        )

        return

    await update.message.reply_text(
        "ℹ️ در این مرحله /skip کاربردی ندارد."
    )


# =========================================================
# /cancel
# =========================================================

async def cancel_command(
    update,
    context,
):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ عملیات لغو شد."
    )

    if is_admin(
        update.effective_user.id
    ):

        await admin_panel(
            update,
            context,
        )


# =========================================================
# خطا
# =========================================================


async def error_handler(
    update,
    context,
):

    print("\n" + "=" * 70)
    print("❌ FILMBIN BOT ERROR")
    print("=" * 70)

    print(
        "ERROR TYPE:",
        type(context.error).__name__
        if context.error
        else "UNKNOWN",
    )

    print(
        "ERROR:",
        repr(context.error),
    )

    print(
        "UPDATE TYPE:",
        type(update).__name__
        if update
        else "None",
    )

    try:

        if update:

            print(
                "UPDATE ID:",
                getattr(update, "update_id", None),
            )

            print(
                "USER:",
                getattr(
                    getattr(update, "effective_user", None),
                    "id",
                    None,
                ),
            )

            print(
                "CHAT:",
                getattr(
                    getattr(update, "effective_chat", None),
                    "id",
                    None,
                ),
            )

            if update.callback_query:

                print(
                    "CALLBACK DATA:",
                    update.callback_query.data,
                )

            if update.message:

                print(
                    "MESSAGE ID:",
                    update.message.message_id,
                )

    except Exception as debug_error:

        print(
            "ERROR WHILE DEBUGGING UPDATE:",
            repr(debug_error),
        )

    print("\nTRACEBACK:")

    traceback.print_exc()

    print("=" * 70 + "\n")

# =========================================================
# اجرای ربات
# =========================================================

async def search_command(
    update,
    context,
):

    context.user_data["search_user"] = True

    await update.message.reply_text(
        "🔎 نام فیلم را بفرست:"
    )


def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set in Railway Variables"
        )

    # ساخت/بررسی دیتابیس
    database.init_db()

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # فایل‌ها و ویدیوهای کانال آرشیو
    # -----------------------------------------------------

    application.add_handler(
        TypeHandler(
            Update,
            archive_media_handler,
        ),
        group=-1,
    )

    # -----------------------------------------------------
    # دستورات
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "search",
            search_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "id",
            id_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "skip",
            skip_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "cancel",
            cancel_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "moviecodes",
            moviecodes_command,
        )
    )

    # -----------------------------------------------------
    # بررسی عضویت
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            check_membership,
            pattern=r"^check:",
        )
    )

    # -----------------------------------------------------
    # راهنمای دریافت
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            guide_button,
            pattern=r"^guide$",
        )
    )

    # -----------------------------------------------------
    # پنل مدیریت
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            admin_button,
            pattern=(
                r"^(admin|add|existing|list|"
                r"list_admin|search|search_admin|"
                r"delete_menu|stats|close)$"
            ),
        )
    )

    # -----------------------------------------------------
    # ثبت فیلم
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            registration_button,
            pattern=r"^(register|restart|cancel)$",
        )
    )

    # -----------------------------------------------------
    # انتشار
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            publish_movie,
            pattern=r"^publish:",
        )
    )

    # -----------------------------------------------------
    # حذف
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            confirm_delete,
            pattern=r"^confirmdel:",
        )
    )

    # -----------------------------------------------------
    # نمایش فیلم
    # -----------------------------------------------------
    
    application.add_handler(
        CallbackQueryHandler(
            movie_view,
            pattern=r"^movie:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            favorite_button,
            pattern=r"^favorite:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            favorites_button,
            pattern=r"^favorites$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            back_home_button,
            pattern=r"^back_home$",
        )
    )
    
    application.add_handler(
        CallbackQueryHandler(
            notification_toggle,
            pattern=r"^notify_(on|off)$",
        )
    )
    
    # -----------------------------------------------------
    # فایل‌ها و عکس‌ها
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            (
                filters.PHOTO
                | filters.VIDEO
                | filters.Document.ALL
            ),
            media_router,
        )
    )

    # -----------------------------------------------------
    # پیام‌های متنی
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router,
        )
    )

    # -----------------------------------------------------
    # مدیریت خطاها
    # -----------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    print(
        "FilmBin bot is running..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()


