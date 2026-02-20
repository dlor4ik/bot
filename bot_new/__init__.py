import gspread
import configs
# Авторизация через сервисный аккаунт
from google.oauth2.service_account import Credentials

# Укажите путь к JSON-файлу с ключами

SERVICE_ACCOUNT_FILE = 'lofty-psyche-447020-e8-943247e4dfe4.json'

# Настройка доступа
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)

# Подключение к Google Таблице
client = gspread.authorize(creds)
spreadsheet = client.open(configs.SHEETS)  # Замените на имя вашей таблицы

sheet = spreadsheet.worksheet(configs.MAIN_SHEET)  # Работаем с основным листом
case_sheet = spreadsheet.worksheet(configs.MAIN_SHEET)  # Работаем с основным листом
tsks_sheet= spreadsheet.worksheet(configs.TASKS_SHEET)  # Работаем с листом для задач
team_sheet= spreadsheet.worksheet(configs.TEAM_SHEET)  # Работаем с листом для команды


print("Лист получен")  