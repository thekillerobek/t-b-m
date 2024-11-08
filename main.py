from aiogram import Bot, Dispatcher, types
from bs4 import BeautifulSoup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
import re
import logging
import hashlib
import asyncio
import math

CHANNELS = '-1002303250066'
bot = Bot(token="7903408500:AAGu6fj6MjUSEY1ae4g8rl810cnj-ULZork")
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# Словарь для хранения соответствия между хэшами и URL
manga_url_mapping = {}

# ________________________ Manga search функция ________________________________ #
async def search_manga_by_title(title):
    search_url = f'https://manga-chan.me/?do=search&subaction=search&story={title}'
    response = requests.get(search_url)

    if response.status_code != 200:
        logging.error(f"Error: status {response.status_code}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    manga_items = soup.find_all('div', class_='content_row')
    manga_list = []
    for item in manga_items:
        raw_title = item.find('div', class_='manga_row1').text.strip()
        
        # Находим текст в скобках
        manga_title_match = re.search(r'\((.*?)\)', raw_title)
        manga_title = manga_title_match.group(1) if manga_title_match else "Не найдено"

        # Формируем URL
        manga_url = item.find('h2').find('a')['href']

        # Создаем хэш для URL и сохраняем его в словаре
        manga_hash = hashlib.md5(manga_url.encode()).hexdigest()
        manga_url_mapping[manga_hash] = manga_url

        # Добавляем найденную мангу в список
        manga_list.append({'manga_title': manga_title, 'manga_hash': manga_hash})

    return manga_list


# ________________________ Manga detail функция ________________________________ #
def detail_manga(manga_url):
    response = requests.get(manga_url)
    if response.status_code != 200:
        print(f"Не удалось получить данные. Код ответа: {response.status_code}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')


    raw_title = soup.find('h1').text.strip()
    manga_title_match = re.search(r'\((.*?)\)', raw_title)
    manga_title = manga_title_match.group(1) if manga_title_match else "Не найдено"

    description_tag = soup.find('div', id='description')
    description = description_tag.text.strip() if description_tag else "Описание не найдено"

    status_tag = soup.find('td', class_='item', text="Статус (Томов)")
    volume_info = status_tag.find_next_sibling('td', class_='item2').text.strip() if status_tag else "Информация о статусе и томах не найдена"

    chapters_kol = soup.find('td', class_='item', text='Загружено')
    chapters_kol = chapters_kol.find_next_sibling('td', class_='item2').text.strip() if chapters_kol else "Количество загруженных глав не найдено"
    
    chapters = []
    for row in soup.find_all('tr'):
        chapter_info = row.find('div', class_='manga2')
        if chapter_info:
            link_tag = chapter_info.find('a')
            if link_tag:
                chapter_name = link_tag.text.strip()
                chapter_url = "https://manga-chan.me" + link_tag['href']
                chapters.append((chapter_name, chapter_url))


    cover_image_url = soup.find('img', id='cover')['src']

    manga_details = {
        "title": manga_title,
        "description": description,
        "volume_info": volume_info,
        "chapters_kol": chapters_kol,
        "chapters": chapters,
        'cover_image_url': cover_image_url,
    }
    return manga_details

# ________________________ Bot start функция ________________________________ #
@dp.message(Command('start'))
async def start(message: types.Message):
    await message.answer(f'Приветь {message.from_user.full_name}! Отправ мне название манги и я найду мангу.')


@dp.message(Command('help'))
async def send_help(message: types.Message):
    help_text = (
        "📖 Вот как я могу помочь:\n\n"
        "1.Манга берётся с сайта manga-chan.me\n\n"
        "Если там нет какого-то манги, то и тут в боте его не будет!\n\n"
        "3. Отправьте название манги, и я найду её для вас.\n\n"
        "4. После поиска выберите нужную мангу из списка, чтобы увидеть её описание и доступные главы.\n\n"
        "5. Используйте кнопки \"⬅️ Назад\" и \"➡️ Далее\" для навигации по главам, если их много.\n\n"
        "Если возникнут вопросы, напишите мне, и я постараюсь помочь! 😊"
    )
    await message.reply(help_text)

# ________________________ Botda manga поиск функция ________________________________ #
@dp.message()
async def search_manga(message: types.Message):
    manga_title = message.text
    manga_search = await search_manga_by_title(manga_title)

    if manga_search is None or len(manga_search) == 0:
        await message.reply("Манга не найдена. Попробуйте другое название.")
        return

    keyboard_builder = InlineKeyboardBuilder() 
    for manga in manga_search:
        keyboard_builder.button(text=manga['manga_title'], callback_data=manga['manga_hash'])
    keyboard_builder.adjust(1)


    await message.reply("Вот что я смог найти: \n", reply_markup=keyboard_builder.as_markup(resize_keyboard=True))

# ________________________ Botda manga detail функция ________________________________ #
# Обновлённая функция для отображения деталей манги с пагинацией
@dp.callback_query()
async def show_manga_details(callback_query: types.CallbackQuery):
    # Проверяем, содержит ли callback_data символ ":"
    if ':' in callback_query.data:
        manga_hash, page = callback_query.data.split(':')
        page = int(page)
    else:
        manga_hash = callback_query.data
        page = 0  # Устанавливаем начальную страницу

    manga_url = manga_url_mapping.get(manga_hash)

    if not manga_url:
        await callback_query.message.reply("Не удалось найти информацию о выбранной манге.")
        return

    manga_details = detail_manga(manga_url)
    if manga_details is None:
        await callback_query.message.reply("Не удалось получить информацию о манге.")
        return

    max_chapters = 10  # Количество глав на странице
    start = page * max_chapters
    end = start + max_chapters
    chapters_to_display = manga_details['chapters'][start:end]

    details_text = (
        f"Название:  {manga_details['title']}\n\n"
        f"📚Описание📚:\n {manga_details['description']}\n\n"
        f"⭕Количество томов⭕:\n {manga_details['volume_info']}\n\n"
        f"💾Загруженные главы💾:\n {manga_details['chapters_kol']}\n\n"
        "Главы:\n"
    )

    keyboard = InlineKeyboardBuilder()
    for chapter_name, chapter_url in chapters_to_display:
        keyboard.button(text=chapter_name, url=chapter_url)
    
    # Добавляем кнопки "Назад" и "Далее" для навигации между страницами
    if page > 0:
        keyboard.button(
            text="⬅️ Назад",
            callback_data=f"{manga_hash}:{page - 1}"
        )
    if end < len(manga_details['chapters']):
        keyboard.button(
            text="➡️ Далее",
            callback_data=f"{manga_hash}:{page + 1}"
        )

    keyboard.adjust(1)

    await callback_query.message.edit_media(
        media=types.InputMediaPhoto(
            media=manga_details['cover_image_url'],
            caption=details_text
        ),
        reply_markup=keyboard.as_markup(resize_keyboard=True)
    )



async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
