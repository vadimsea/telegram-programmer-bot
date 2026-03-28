"""
Фоновый модуль для автоматической публикации обучающих постов
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

try:
    from config import TELEGRAM_GROUP_USERNAME, TELEGRAM_TOKEN  # type: ignore
except Exception:
    raw_group_username = os.getenv('TELEGRAM_GROUP_USERNAME', '@learncoding_team') or '@learncoding_team'
    raw_group_username = raw_group_username.strip() or '@learncoding_team'
    if not raw_group_username.startswith('@'):
        raw_group_username = f'@{raw_group_username}'
    TELEGRAM_GROUP_USERNAME = raw_group_username
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('BOT_TOKEN')

# Конфигурация - используем TELEGRAM_TOKEN из config, fallback на BOT_TOKEN для совместимости
BOT_TOKEN = TELEGRAM_TOKEN if 'TELEGRAM_TOKEN' in locals() else (os.getenv('TELEGRAM_TOKEN') or os.getenv('BOT_TOKEN'))
CHAT_ID = os.getenv('CHAT_ID')
PERIOD_DAYS = int(os.getenv('PERIOD_DAYS', '4'))
TZ = os.getenv('TZ', 'Europe/Minsk')
COURSE_SCHEDULER_ENABLED = os.getenv('COURSE_SCHEDULER_ENABLED', '0') == '1'
STATE_FILE = os.getenv('STATE_FILE', 'state.json')

# Данные уроков
HTML_CSS_LESSONS = [
    {
        "title": "Структура HTML-документа, заголовки, абзацы, ссылки, изображения",
        "theory": """<b>Что такое HTML?</b>
HTML (HyperText Markup Language) — это язык разметки, который создает структуру веб-страниц. Представьте HTML как скелет сайта, который определяет, где что находится.

<b>🔹 ОСНОВНАЯ СТРУКТУРА:</b>
Каждый HTML-документ начинается с DOCTYPE html и содержит:
• <code>html</code> — корневой элемент (обертка для всего)
• <code>head</code> — метаданные (заголовок, кодировка, стили)
• <code>body</code> — видимый контент страницы

<b>🔹 ОСНОВНЫЕ ЭЛЕМЕНТЫ:</b>
• <b>Заголовки:</b> <code>h1</code> (самый важный) до <code>h6</code> (наименее важный)
• <b>Абзацы:</b> <code>p</code> для текста
• <b>Ссылки:</b> <code>a href="URL"</code>текст ссылки<code>/a</code>
• <b>Изображения:</b> <code>img src="путь" alt="описание"</code>

<b>🔹 ВАЖНО ПОМНИТЬ:</b>
• Теги бывают парные: <code>тег</code>контент<code>/тег</code>
• И одиночные: <code>img</code> или <code>br</code>
• Всегда закрывайте парные теги!
• Используйте alt для изображений (доступность)

<b>⚡ Быстрый тест:</b> нажми кнопку ниже — в личку бот пришлёт 1–2 вопроса с вариантами (без длинных ответов).""",
        "homework": """<b>ПРАКТИЧЕСКОЕ ЗАДАНИЕ:</b>
Создайте свою первую веб-страницу "О себе":

<b>📋 ЧТО НУЖНО СДЕЛАТЬ:</b>
1. Начните с базовой структуры HTML
2. Добавьте заголовок h1 с вашим именем
3. Напишите 2-3 абзаца о себе
4. Добавьте ссылку на ваш профиль в соцсетях
5. Вставьте ваше фото (или любое изображение)
6. Используйте семантические теги: header, main, section

<b>📝 ПРИМЕР СТРУКТУРЫ:</b>
<code>DOCTYPE html
html
head
    title Моя страница /title
/head
body
    header
        h1 Привет! Меня зовут [Ваше имя] /h1
    /header
    main
        section
            p Здесь расскажите о себе... /p
        /section
    /main
/body
/html</code>

<b>✅ КРИТЕРИИ ОЦЕНКИ:</b>
• Правильная структура HTML
• Использование семантических тегов
• Корректное закрытие всех тегов
• Наличие атрибута alt у изображения"""
    },
    {
        "title": "Списки, таблицы, семантические теги",
        "theory": """Структурирование контента — ключ к созданию понятных и доступных веб-страниц.

🔹 СПИСКИ:
• Маркированный список: ul (unordered list)
  li Пункт 1 /li
  li Пункт 2 /li
/ul

• Нумерованный список: ol (ordered list)
  li Первый пункт /li
  li Второй пункт /li
/ol

🔹 ТАБЛИЦЫ:
Таблицы состоят из строк и ячеек:
table
  tr (table row — строка)
    th Заголовок /th (table header)
    td Данные /td (table data)
  /tr
/table

🔹 СЕМАНТИЧЕСКИЕ ТЕГИ:
Это теги, которые описывают СМЫСЛ контента:
• header — шапка сайта
• nav — навигация
• main — основной контент
• section — раздел
• article — статья
• aside — боковая панель
• footer — подвал

ПОЧЕМУ ЭТО ВАЖНО:
- Поисковики лучше понимают структуру
- Скрин-ридеры помогают слепым пользователям
- Код становится понятнее""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте страницу "Мой блог":

1. Используйте семантические теги для структуры
2. Добавьте навигационное меню с 3 пунктами
3. Создайте статью с заголовком и текстом
4. Добавьте боковую панель с интересными фактами
5. Вставьте таблицу с вашими любимыми фильмами:
   Колонки: Название | Год | Рейтинг
6. Добавьте список ваших хобби

СТРУКТУРА:
header
  navМеню/nav
/header
main
  articleСтатья/article
  asideБоковая панель/aside
/main
footerПодвал/footer"""
    },
    {
        "title": "Подключение CSS, селекторы, наследование",
        "theory": """CSS (Cascading Style Sheets) — это язык стилей, который делает ваши HTML-страницы красивыми!

🔹 СПОСОБЫ ПОДКЛЮЧЕНИЯ CSS:

1. INLINE (в строке):
   p style="color: red;"Красный текст/p

2. ВНУТРЕННИЙ (в head):
   style
     p { color: blue; }
   /style

3. ВНЕШНИЙ (отдельный файл) — ЛУЧШИЙ СПОСОБ:
   link rel="stylesheet" href="style.css"

🔹 СЕЛЕКТОРЫ — как выбрать элементы:

• По тегу: p { } — все абзацы
• По классу: .my-class { } — элементы с class="my-class"
• По ID: #my-id { } — элемент с id="my-id"
• По атрибуту: [href] { } — все ссылки

🔹 НАСЛЕДОВАНИЕ:
Дочерние элементы наследуют стили от родителей:
body { font-family: Arial; } — все элементы внутри body получат этот шрифт

🔹 КАСКАД (приоритет):
1. Inline стили (самый высокий приоритет)
2. ID селекторы
3. Классы
4. Теги (самый низкий приоритет)""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте стильную страницу:

1. Создайте HTML-файл и отдельный CSS-файл
2. Подключите CSS к HTML
3. Используйте разные селекторы:
   - Стилизуйте все заголовки h1
   - Создайте класс .highlight для выделения текста
   - Добавьте ID #main-title для главного заголовка
4. Покажите наследование:
   - Установите шрифт для body
   - Убедитесь, что все элементы его наследуют
5. Покажите каскад:
   - Создайте конфликт стилей и посмотрите, какой победит

ПРИМЕР CSS:
body {
    font-family: Arial, sans-serif;
    background-color: #f0f0f0;
}

h1 {
    color: #333;
    text-align: center;
}

.highlight {
    background-color: yellow;
    font-weight: bold;
}

#main-title {
    font-size: 2em;
    color: blue;
}"""
    },
    {
        "title": "Блочная модель: margin, padding, border, display",
        "theory": """Блочная модель — это основа понимания того, как браузер отображает элементы на странице.

🔹 СТРУКТУРА ЭЛЕМЕНТА:
Каждый HTML-элемент — это прямоугольник из 4 частей:

┌─────────────────────────────────┐ ← margin (внешние отступы)
│ ┌─────────────────────────────┐ │
│ │ ┌─────────────────────────┐ │ │ ← border (граница)
│ │ │ ┌─────────────────────┐ │ │ │
│ │ │ │     CONTENT         │ │ │ │ ← content (содержимое)
│ │ │ │   (текст, картинки)  │ │ │ │
│ │ │ └─────────────────────┘ │ │ │
│ │ └─────────────────────────┘ │ │ ← padding (внутренние отступы)
│ └─────────────────────────────┘ │
└─────────────────────────────────┘

🔹 СВОЙСТВА:
• margin — расстояние от элемента до других элементов
• border — граница вокруг элемента
• padding — расстояние от границы до содержимого
• content — сам контент (текст, изображения)

🔹 DISPLAY — как элемент отображается:
• block — занимает всю ширину, начинается с новой строки
• inline — занимает только нужную ширину, в одной строке
• inline-block — как inline, но можно задать размеры
• flex — гибкая раскладка (изучаем позже)
• grid — сеточная раскладка (изучаем позже)""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте "визуальную лабораторию" блочной модели:

1. Создайте 3 блока с разными стилями:
   Блок 1: margin: 20px, padding: 10px, border: 2px solid red
   Блок 2: margin: 10px, padding: 20px, border: 1px dashed blue
   Блок 3: margin: 5px, padding: 5px, border: 3px dotted green

2. Покажите разницу между display:
   - Создайте элементы с display: block
   - Создайте элементы с display: inline
   - Создайте элементы с display: inline-block

3. Добавьте фоновые цвета, чтобы видеть границы:
   background-color: lightblue;

ПРИМЕР CSS:
.block1 {
    margin: 20px;
    padding: 10px;
    border: 2px solid red;
    background-color: lightcoral;
    display: block;
}

.inline-element {
    display: inline;
    background-color: lightgreen;
    margin: 5px;
    padding: 5px;
    border: 1px solid black;
}"""
    },
    {
        "title": "Flexbox и сетки",
        "theory": """Flexbox и Grid — это современные инструменты для создания красивых и адаптивных макетов!

🔹 FLEXBOX — одномерная раскладка:
Flexbox идеален для выравнивания элементов в одном направлении (горизонтально или вертикально).

ОСНОВНЫЕ СВОЙСТВА:
• display: flex — включаем flexbox
• flex-direction: row/column — направление (строка/столбец)
• justify-content — выравнивание по главной оси
• align-items — выравнивание по поперечной оси
• flex-wrap — перенос элементов

🔹 CSS GRID — двумерная раскладка:
Grid позволяет создавать сложные сетки с точным контролем позиций.

ОСНОВНЫЕ СВОЙСТВА:
• display: grid — включаем grid
• grid-template-columns — количество и размер колонок
• grid-template-rows — количество и размер строк
• grid-gap — расстояние между элементами
• grid-area — именованные области

🔹 КОГДА ИСПОЛЬЗОВАТЬ:
• Flexbox — для навигации, кнопок, выравнивания
• Grid — для сложных макетов страниц, карточек""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте современный макет страницы:

1. НАВИГАЦИЯ (Flexbox):
   - Создайте горизонтальное меню с логотипом слева и ссылками справа
   - Используйте justify-content: space-between
   - Добавьте выравнивание по центру

2. ОСНОВНОЙ КОНТЕНТ (Grid):
   - Создайте сетку 3x2 (3 колонки, 2 строки)
   - Разместите статьи в ячейках
   - Добавьте отступы между элементами

3. АДАПТИВНОСТЬ:
   - На мобильных: 1 колонка
   - На планшетах: 2 колонки
   - На десктопе: 3 колонки

ПРИМЕР CSS:
.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
}

.grid-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-gap: 20px;
    padding: 20px;
}

@media (max-width: 768px) {
    .grid-container {
        grid-template-columns: 1fr;
    }
}"""
    },
    {
        "title": "Медиа-запросы, адаптивность",
        "theory": """Адаптивный дизайн — это создание сайтов, которые отлично выглядят на любом устройстве!

🔹 ЧТО ТАКОЕ МЕДИА-ЗАПРОСЫ:
Медиа-запросы позволяют применять разные стили в зависимости от характеристик устройства.

СИНТАКСИС:
@media (условие) {
    /* стили применяются только при выполнении условия */
}

🔹 ОСНОВНЫЕ УСЛОВИЯ:
• max-width: 768px — экраны до 768px (мобильные)
• min-width: 769px — экраны от 769px (планшеты и больше)
• orientation: portrait — портретная ориентация
• orientation: landscape — альбомная ориентация

🔹 MOBILE-FIRST ПОДХОД:
1. Сначала создаем стили для мобильных
2. Затем добавляем стили для больших экранов
3. Используем min-width вместо max-width

🔹 BREAKPOINTS (точки перелома):
• 320px — маленькие мобильные
• 768px — планшеты
• 1024px — ноутбуки
• 1200px — десктопы""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте полностью адаптивную страницу:

1. БАЗОВЫЕ СТИЛИ (мобильные):
   - Одна колонка
   - Большие кнопки и ссылки
   - Простая навигация

2. ПЛАНШЕТЫ (768px+):
   - Две колонки
   - Более компактные элементы
   - Горизонтальное меню

3. ДЕСКТОПЫ (1024px+):
   - Три колонки
   - Боковая панель
   - Расширенная навигация

ПРИМЕР CSS:
/* Мобильные (базовые стили) */
.container {
    width: 100%;
    padding: 10px;
}

/* Планшеты */
@media (min-width: 768px) {
    .container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }
}

/* Десктопы */
@media (min-width: 1024px) {
    .container {
        grid-template-columns: 1fr 1fr 1fr;
    }
}"""
    }
]

JAVASCRIPT_LESSONS = [
    {
        "title": "Подключение JS, переменные, типы данных",
        "theory": """JavaScript — это язык программирования, который делает веб-страницы интерактивными!

🔹 ПОДКЛЮЧЕНИЕ JAVASCRIPT:

1. ВНУТРЕННИЙ (в HTML):
   script
     alert('Привет!');
   /script

2. ВНЕШНИЙ (отдельный файл) — ЛУЧШИЙ СПОСОБ:
   script src="script.js"/script

🔹 ПЕРЕМЕННЫЕ — контейнеры для данных:
let имя = 'Вадим';        // можно изменить
const возраст = 25;       // нельзя изменить
var старый_способ = 'не используйте'; // устаревший

🔹 ТИПЫ ДАННЫХ:
• string (строка): "Привет", 'Мир'
• number (число): 42, 3.14, -10
• boolean (логический): true, false
• undefined: переменная не имеет значения
• null: переменная пустая

🔹 ОПЕРАТОРЫ:
• + — сложение или конкатенация строк
• - — вычитание
• * — умножение
• / — деление
• == — сравнение (не строгое)
• === — строгое сравнение (лучше!)

ПРИМЕР:
let имя = 'Анна';
let возраст = 20;
let приветствие = 'Привет, ' + имя + '!';
console.log(приветствие); // Выведет: Привет, Анна!""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте интерактивную страницу "Калькулятор возраста":

1. Создайте HTML-форму с полями:
   - Имя пользователя
   - Год рождения
   - Кнопка "Рассчитать"

2. Напишите JavaScript код:
   - Получите данные из формы
   - Вычислите возраст
   - Выведите результат

3. Добавьте проверки:
   - Проверьте, что поля заполнены
   - Проверьте, что год рождения разумный

ПРИМЕР КОДА:
function calculateAge() {
    let name = document.getElementById('name').value;
    let birthYear = document.getElementById('birthYear').value;
    
    if (name === '' || birthYear === '') {
        alert('Заполните все поля!');
        return;
    }
    
    let currentYear = new Date().getFullYear();
    let age = currentYear - birthYear;
    
    let result = name + ', вам ' + age + ' лет!';
    document.getElementById('result').innerHTML = result;
}"""
    },
    {
        "title": "Условия и циклы",
        "theory": """Условия и циклы — это основа программирования! Они позволяют создавать логику и повторять действия.

🔹 УСЛОВНЫЕ ОПЕРАТОРЫ:

IF-ELSE — принимаем решения:
if (условие) {
    // код выполнится, если условие true
} else {
    // код выполнится, если условие false
}

ПРИМЕР:
let возраст = 18;
if (возраст >= 18) {
    console.log('Вы совершеннолетний');
} else {
    console.log('Вы несовершеннолетний');
}

🔹 ЛОГИЧЕСКИЕ ОПЕРАТОРЫ:
• && — И (оба условия должны быть true)
• || — ИЛИ (хотя бы одно условие должно быть true)
• ! — НЕ (инвертирует результат)

🔹 ЦИКЛЫ — повторяем действия:

FOR — когда знаем количество повторений:
for (let i = 0; i  5; i++) {
    console.log('Итерация ' + i);
}

WHILE — когда не знаем количество:
let счетчик = 0;
while (счетчик < 3) {
    console.log('Счетчик: ' + счетчик);
    счетчик++;
}

🔹 ТЕРНАРНЫЙ ОПЕРАТОР — краткая форма if-else:
let результат = условие ? 'да' : 'нет';""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте "Умный калькулятор оценок":

1. ПРОВЕРКА ЧИСЛА:
   - Попросите пользователя ввести число
   - Проверьте, четное оно или нечетное
   - Выведите результат

2. ПОИСК МАКСИМУМА:
   - Попросите ввести 3 числа
   - Найдите и выведите наибольшее

3. ТАБЛИЦА УМНОЖЕНИЯ:
   - Используйте цикл for
   - Выведите таблицу умножения на 7
   - Формат: "7 x 1 = 7", "7 x 2 = 14"...

4. ИГРА "УГАДАЙ ЧИСЛО":
   - Загадайте число от 1 до 10
   - Используйте цикл while
   - Позвольте пользователю угадывать
   - Подсказывайте "больше" или "меньше"

ПРИМЕР КОДА:
// Проверка четности
let число = prompt('Введите число:');
if (число % 2 === 0) {
    alert('Число четное');
} else {
    alert('Число нечетное');
}

// Таблица умножения
for (let i = 1; i <= 10; i++) {
    console.log('7 x ' + i + ' = ' + (7 * i));
}"""
    },
    {
        "title": "Массивы и функции",
        "theory": """Массивы и функции — это мощные инструменты для организации и переиспользования кода!

🔹 МАССИВЫ — списки данных:
let фрукты = ['яблоко', 'банан', 'апельсин'];
let числа = [1, 2, 3, 4, 5];

ОСНОВНЫЕ МЕТОДЫ:
• push() — добавить в конец
• pop() — удалить с конца
• length — количество элементов
• indexOf() — найти индекс элемента
• slice() — скопировать часть массива

🔹 ФУНКЦИИ — переиспользуемые блоки кода:

ОБЫЧНАЯ ФУНКЦИЯ:
function приветствие(имя) {
    return 'Привет, ' + имя + '!';
}

СТРЕЛОЧНАЯ ФУНКЦИЯ (современный способ):
const приветствие = (имя) = {
    return 'Привет, ' + имя + '!';
};

🔹 ПАРАМЕТРЫ И ВОЗВРАТ:
• Параметры — данные, которые функция получает
• return — что функция возвращает
• Функция может не возвращать ничего (void)

🔹 МЕТОДЫ МАССИВОВ:
• map() — преобразовать каждый элемент
• filter() — отфильтровать элементы
• reduce() — свести к одному значению
• forEach() — выполнить действие для каждого""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте "Систему управления задачами":

1. СОЗДАЙТЕ МАССИВ ЗАДАЧ:
   let задачи = ['Купить хлеб', 'Сделать уроки', 'Погулять с собакой'];

2. НАПИШИТЕ ФУНКЦИИ:
   - добавитьЗадачу(текст) — добавляет новую задачу
   - удалитьЗадачу(индекс) — удаляет задачу по индексу
   - показатьЗадачи() — выводит все задачи
   - найтиЗадачу(текст) — ищет задачу по тексту

3. ИСПОЛЬЗУЙТЕ МЕТОДЫ МАССИВОВ:
   - Создайте функцию для подсчета задач
   - Создайте функцию для фильтрации выполненных задач
   - Используйте map() для добавления статуса к задачам

ПРИМЕР КОДА:
let задачи = [];

function добавитьЗадачу(текст) {
    задачи.push(текст);
    console.log('Задача добавлена: ' + текст);
}

function показатьЗадачи() {
    задачи.forEach((задача, индекс) => {
        console.log((индекс + 1) + '. ' + задача);
    });
}

// Использование методов массивов
let задачиССтатусом = задачи.map(задача => ({
    текст: задача,
    выполнена: false
}));"""
    },
    {
        "title": "DOM и события",
        "theory": """DOM и события — это то, что делает веб-страницы интерактивными!

🔹 DOM (Document Object Model):
DOM — это представление HTML-страницы в виде дерева объектов, с которыми может работать JavaScript.

ОСНОВНЫЕ МЕТОДЫ:
• getElementById('id') — найти элемент по ID
• querySelector('.класс') — найти элемент по селектору
• innerHTML — получить/установить HTML содержимое
• textContent — получить/установить текстовое содержимое
• style — изменить CSS стили

🔹 СОБЫТИЯ — реакции на действия пользователя:

ОСНОВНЫЕ СОБЫТИЯ:
• click — клик мышью
• mouseover — наведение мыши
• keydown — нажатие клавиши
• input — ввод текста
• submit — отправка формы

🔹 ОБРАБОТЧИКИ СОБЫТИЙ:
addEventListener — современный способ:
element.addEventListener('click', function() {
    // код выполнится при клике
});

СТАРЫЙ СПОСОБ:
element.onclick = function() {
    // код выполнится при клике
};

🔹 ПРИМЕРЫ ИЗМЕНЕНИЯ DOM:
document.getElementById('title').innerHTML = 'Новый заголовок';
document.querySelector('.box').style.backgroundColor = 'red';
document.body.style.fontSize = '20px';""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте "Интерактивную панель управления":

1. СОЗДАЙТЕ HTML:
   - Кнопка "Изменить цвет фона"
   - Кнопка "Увеличить шрифт"
   - Кнопка "Добавить элемент"
   - Поле ввода для текста
   - Контейнер для новых элементов

2. НАПИШИТЕ JAVASCRIPT:
   - При клике на кнопку цвета — меняйте фон страницы
   - При клике на кнопку шрифта — увеличивайте размер текста
   - При клике на "Добавить элемент" — создавайте новый div с текстом
   - При вводе в поле — показывайте количество символов

3. ДОБАВЬТЕ АНИМАЦИИ:
   - Плавное изменение цветов
   - Анимацию появления новых элементов

ПРИМЕР КОДА:
// Изменение цвета фона
document.getElementById('colorBtn').addEventListener('click', function() {
    let colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4'];
    let randomColor = colors[Math.floor(Math.random() * colors.length)];
    document.body.style.backgroundColor = randomColor;
});

// Добавление нового элемента
document.getElementById('addBtn').addEventListener('click', function() {
    let text = document.getElementById('textInput').value;
    if (text) {
        let newElement = document.createElement('div');
        newElement.textContent = text;
        newElement.className = 'new-item';
        document.getElementById('container').appendChild(newElement);
    }
});"""
    },
    {
        "title": "Работа с JSON и fetch()",
        "theory": """JSON и fetch() — это инструменты для работы с данными из интернета!

🔹 JSON (JavaScript Object Notation):
JSON — это формат для хранения и передачи данных. Выглядит как JavaScript объект, но это строка.

ПРИМЕР JSON:
{
    "имя": "Анна",
    "возраст": 25,
    "хобби": ["чтение", "программирование"]
}

🔹 МЕТОДЫ РАБОТЫ С JSON:
• JSON.stringify() — объект → JSON строка
• JSON.parse() — JSON строка → объект

ПРИМЕР:
let объект = { имя: 'Вадим', возраст: 30 };
let jsonСтрока = JSON.stringify(объект);
let обратно = JSON.parse(jsonСтрока);

🔹 FETCH API — загрузка данных:
fetch() позволяет получать данные с сервера.

БАЗОВОЕ ИСПОЛЬЗОВАНИЕ:
fetch('https://api.example.com/data')
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Ошибка:', error));

🔹 ASYNC/AWAIT — современный способ:
async function загрузитьДанные() {
    try {
        let response = await fetch('https://api.example.com/data');
        let data = await response.json();
        return data;
    } catch (error) {
        console.error('Ошибка загрузки:', error);
    }
}

🔹 ОБРАБОТКА ОШИБОК:
Всегда проверяйте статус ответа и обрабатывайте ошибки!""",
        "homework": """ПРАКТИЧЕСКОЕ ЗАДАНИЕ:
Создайте "Приложение погоды":

1. ИСПОЛЬЗУЙТЕ ПУБЛИЧНЫЙ API:
   - OpenWeatherMap API (бесплатный)
   - Или JSONPlaceholder для тестирования

2. СОЗДАЙТЕ ФУНКЦИИ:
   - загрузитьПогоду(город) — получает данные о погоде
   - отобразитьПогоду(данные) — показывает погоду на странице
   - обработатьОшибку(ошибка) — показывает сообщение об ошибке

3. ДОБАВЬТЕ ИНТЕРФЕЙС:
   - Поле ввода для города
   - Кнопка "Получить погоду"
   - Блок для отображения данных
   - Индикатор загрузки

4. ОБРАБОТАЙТЕ ОШИБКИ:
   - Неверный город
   - Проблемы с интернетом
   - Ошибки API

ПРИМЕР КОДА:
async function загрузитьПогоду(город) {
    try {
        let response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${город}&appid=YOUR_API_KEY`);
        
        if (!response.ok) {
            throw new Error('Город не найден');
        }
        
        let данные = await response.json();
        отобразитьПогоду(данные);
    } catch (ошибка) {
        обработатьОшибку(ошибка);
    }
}

function отобразитьПогоду(данные) {
    let температура = Math.round(данные.main.temp - 273.15);
    let описание = данные.weather[0].description;
    
    document.getElementById('погода').innerHTML = `
        h2Погода в ${данные.name}/h2
        pТемпература: ${температура}°C/p
        pОписание: ${описание}/p
    `;
}"""
    },
    {
        "title": "Мини-проект: интерактивная галерея",
        "theory": """Поздравляем! Вы изучили основы веб-разработки! Теперь создадим финальный проект, объединяющий все знания.

🔹 ЧТО МЫ ИЗУЧИЛИ:
• HTML — структура страницы
• CSS — стили и адаптивность  
• JavaScript — интерактивность
• DOM — работа с элементами
• События — реакции на действия
• JSON — работа с данными

🔹 ФИНАЛЬНЫЙ ПРОЕКТ — "Интерактивная галерея":
Этот проект покажет, как все технологии работают вместе.

ФУНКЦИИ ГАЛЕРЕИ:
• Просмотр изображений в полном размере
• Фильтрация по категориям
• Добавление новых изображений
• Удаление элементов
• Сохранение данных в localStorage

🔹 АРХИТЕКТУРА ПРОЕКТА:
• Модульная структура кода
• Разделение на функции
• Обработка ошибок
• Адаптивный дизайн
• Современный JavaScript

🔹 ТЕХНОЛОГИИ:
• HTML5 семантика
• CSS Grid/Flexbox
• ES6+ JavaScript
• LocalStorage API
• Event Delegation""",
        "homework": """ФИНАЛЬНЫЙ ПРОЕКТ:
Создайте "Интерактивную галерею изображений":

1. СТРУКТУРА HTML:
   - Заголовок с названием галереи
   - Панель фильтров (Все, Природа, Города, Люди)
   - Сетка изображений
   - Модальное окно для просмотра
   - Форма добавления новых изображений

2. СТИЛИ CSS:
   - Адаптивная сетка изображений
   - Красивые карточки с hover-эффектами
   - Модальное окно с затемнением
   - Анимации появления/исчезновения

3. ФУНКЦИИ JAVASCRIPT:
   - загрузитьГалерею() — загружает изображения
   - отфильтроватьГалерею(категория) — фильтрует по категориям
   - показатьИзображение(изображение) — открывает в модальном окне
   - добавитьИзображение(данные) — добавляет новое изображение
   - удалитьИзображение(id) — удаляет изображение
   - сохранитьВЛокальноеХранилище() — сохраняет данные

4. ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ:
   - Поиск по названию
   - Сортировка по дате добавления
   - Предпросмотр перед добавлением
   - Валидация форм

ПРИМЕР СТРУКТУРЫ:
let галерея = {
    изображения: [],
    текущийФильтр: 'все',
    
    инициализация() {
        this.загрузитьИзЛокальногоХранилища();
        this.отобразитьИзображения();
        this.настроитьСобытия();
    }
};

ПОЗДРАВЛЯЕМ! Вы создали полноценное веб-приложение! 🎉"""
    }
]

class CourseScheduler:
    """Планировщик курса"""
    
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
        self.scheduler = AsyncIOScheduler(timezone=TZ)
        self.current_index = self.load_index()
        
    def load_index(self) -> int:
        """Загрузить текущий индекс урока"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('lesson_index', 0)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки индекса урока: {e}")
            logger.error(f"🔧 Создаю новый файл состояния...")
        return 0
    
    def save_index(self, index: int):
        """Сохранить текущий индекс урока"""
        try:
            data = {'lesson_index': index, 'last_updated': datetime.now().isoformat()}
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения индекса урока: {e}")
            logger.error(f"🔧 Проверьте права доступа к файлу {STATE_FILE}")
    
    def make_lesson(self, idx: int) -> Dict[str, str]:
        """Создать урок по индексу (циклически)"""
        # Определяем тип урока (HTML/CSS или JavaScript)
        lesson_type = "HTML/CSS" if (idx // len(HTML_CSS_LESSONS)) % 2 == 0 else "JavaScript"
        
        if lesson_type == "HTML/CSS":
            lesson_data = HTML_CSS_LESSONS[idx % len(HTML_CSS_LESSONS)]
            lesson_num = (idx % len(HTML_CSS_LESSONS)) + 1
        else:
            lesson_data = JAVASCRIPT_LESSONS[idx % len(JAVASCRIPT_LESSONS)]
            lesson_num = (idx % len(JAVASCRIPT_LESSONS)) + 1
        
        # Формируем домашнее задание на основе темы
        if lesson_type == "HTML/CSS":
            hw = f"Сверстайте {lesson_data['homework'].lower()}"
        else:
            hw = f"Напишите {lesson_data['homework'].lower()}"
        
        return {
            'title': f"Урок {idx + 1}. {lesson_data['title']}",
            'text': lesson_data['theory'],
            'hw': hw,
            'type': lesson_type
        }
    
    async def post_lesson(self):
        """Опубликовать урок"""
        if not self.bot or not CHAT_ID:
            logger.error("❌ Бот или CHAT_ID не настроены")
            logger.error("🔧 Проверьте настройки в .env файле")
            return
        
        try:
            lesson = self.make_lesson(self.current_index)
            
            # Формируем красивый текст сообщения на русском
            message_text = (
                f"👋 <b>Привет!</b> Добро пожаловать на урок!\n\n"
                f"📚 <b>{lesson['title']}</b>\n\n"
                f"💡 <b>Теория:</b>\n{lesson['text']}\n\n"
                f"📝 <b>Домашнее задание:</b>\n{lesson['hw']}\n\n"
                f"✅ <b>Сдаём ДЗ:</b> ответом на это сообщение в этой же группе\n\n"
                f"🎯 <b>Уровень:</b> {lesson['type']}\n"
                f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}"
            )
            
            # Создаем красивую кнопку
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "👨‍💻 Связаться с ментором — бесплатно", 
                    url="https://t.me/vadzim_belarus"
                )],
                [InlineKeyboardButton(
                    "📚 Все уроки курса", 
                    url="https://t.me/learncoding_team"
                )],
                [InlineKeyboardButton(
                    "🌐 Сайт создателя",
                    url="https://vadzim.by"
                )],
                [InlineKeyboardButton(
                    "⚡ Быстрый тест (30 сек)",
                    callback_data=f"check_theory_{self.current_index}"
                )]
            ])
            
            # Отправляем сообщение
            message = await self.bot.send_message(
                chat_id=CHAT_ID,
                text=message_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            # Пытаемся закрепить сообщение (игнорируем ошибки)
            try:
                await self.bot.pin_chat_message(
                    chat_id=CHAT_ID,
                    message_id=message.message_id
                )
            except TelegramError as e:
                logger.warning(f"⚠️ Не удалось закрепить сообщение: {e}")
                logger.warning(f"🔧 Убедитесь, что бот является администратором группы")
            
            # Красивое логирование на русском
            logger.info(f"🎓 Опубликован урок {self.current_index + 1} ({lesson['type']})")
            logger.info(f"📖 Тема: {lesson['title']}")
            logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y в %H:%M')}")
            logger.info(f"👥 Группа: {TELEGRAM_GROUP_USERNAME}")
            
            # Обновляем индекс и сохраняем
            self.current_index += 1
            self.save_index(self.current_index)
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации урока: {e}")
            logger.error(f"🔧 Проверьте подключение к Telegram API")
    
    def setup_scheduler(self):
        """Настроить планировщик"""
        if not COURSE_SCHEDULER_ENABLED:
            logger.info("⏸️ Планировщик курса отключен в настройках")
            logger.info("🔧 Для включения установите COURSE_SCHEDULER_ENABLED=1 в .env")
            return
        
        if not BOT_TOKEN or not CHAT_ID:
            logger.error("❌ BOT_TOKEN или CHAT_ID не настроены в .env файле")
            logger.error("🔧 Проверьте настройки: BOT_TOKEN и CHAT_ID")
            return
        
        # Планируем первый урок через 5 секунд
        self.scheduler.add_job(
            self.post_lesson,
            'date',
            run_date=datetime.now() + timedelta(seconds=5),
            id='first_lesson'
        )
        
        # Планируем повторяющиеся уроки каждые 4 дня
        self.scheduler.add_job(
            self.post_lesson,
            IntervalTrigger(days=PERIOD_DAYS),
            id='recurring_lessons'
        )
        
        logger.info(f"🚀 Планировщик курса запущен!")
        logger.info(f"📅 Период публикации: каждые {PERIOD_DAYS} дней")
        logger.info(f"🌍 Часовой пояс: {TZ}")
        logger.info(f"👥 Целевая группа: {TELEGRAM_GROUP_USERNAME}")
        logger.info(f"⏰ Первый урок через 5 секунд...")
    
    async def run_forever(self):
        """Запустить планировщик навсегда"""
        self.setup_scheduler()
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Планировщик курса успешно запущен!")
            logger.info(f"🎓 Готов публиковать уроки в группе {TELEGRAM_GROUP_USERNAME}")
        
        # Держим процесс живым
        try:
            while True:
                await asyncio.sleep(60)  # Проверяем каждую минуту
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
            logger.info("📚 Останавливаем планировщик курса...")
            self.scheduler.shutdown()
            logger.info("✅ Планировщик успешно остановлен")


# Глобальный экземпляр планировщика
scheduler = CourseScheduler()

async def run_forever():
    """Публичная функция для запуска планировщика"""
    await scheduler.run_forever()
