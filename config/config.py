import configparser
import os

# получаем путь к директории проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# инициализируем конфиг из config.ini
conf = configparser.ConfigParser()
conf.read(os.path.join(BASE_DIR, 'config', 'config.ini'), encoding='utf-8')


def get_config_value(section, key):
    value_raw = conf.get(section, key)

    if value_raw.startswith('${') and value_raw.endswith('}'):
        env_var_name = value_raw[2:-1]
        value = os.getenv(env_var_name)
    else:
        value = value_raw

    return value
