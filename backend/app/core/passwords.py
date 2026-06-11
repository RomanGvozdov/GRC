"""Перевірка пароля проти локального словника поширених/витеклих паролів.

Список базується на найпоширеніших паролях з публічних витоків (rockyou,
SecLists top lists). Порівняння нечутливе до регістру; також відсікаються
паролі, що складаються з поширеної основи з типовими суфіксами (123, !, 2024…).
"""

COMMON_PASSWORDS = {
    "password", "passw0rd", "password1", "password123", "p@ssword", "p@ssw0rd",
    "qwerty", "qwerty123", "qwertyuiop", "qwerty12345", "1q2w3e4r", "1q2w3e4r5t",
    "123456", "1234567", "12345678", "123456789", "1234567890", "12345678910",
    "111111", "000000", "121212", "654321", "987654321", "112233", "123123",
    "abc123", "abcd1234", "a1b2c3d4", "aaa111", "asdfgh", "asdfghjkl", "zxcvbnm",
    "iloveyou", "sunshine", "princess", "welcome", "welcome1", "letmein",
    "monkey", "dragon", "football", "baseball", "superman", "batman", "master",
    "shadow", "killer", "trustno1", "whatever", "freedom", "secret", "summer",
    "starwars", "pokemon", "michael", "jordan", "charlie", "daniel", "andrew",
    "jessica", "ashley", "nicole", "hannah", "matthew", "access", "mustang",
    "michelle", "tigger", "flower", "jennifer", "joshua", "hunter", "ginger",
    "computer", "internet", "samsung", "google", "apple123", "windows",
    "admin", "admin123", "administrator", "root", "toor", "user", "guest",
    "test", "test123", "testtest", "demo", "changeme", "default", "system",
    "pass", "pass123", "love", "lovely", "loveme", "babygirl", "angel",
    "hello", "hello123", "hellokitty", "happy", "cookie", "chocolate",
    "11111111", "22222222", "0987654321", "qazwsx", "qazwsxedc", "1qaz2wsx",
    "zaq12wsx", "q1w2e3r4", "q1w2e3r4t5", "5555555", "7777777", "88888888",
    "987654", "55555", "999999999", "147258369", "159753", "131313",
    "699669", "696969", "666666", "777777", "midnight", "bailey", "passion",
    "biteme", "blink182", "rockyou", "soccer", "hockey", "hottie", "harley",
    "ranger", "buster", "thomas", "robert", "george", "pepper", "maggie",
    "cheese", "peanut", "pussycat", "scooter", "snoopy", "snickers",
    "minecraft", "fortnite", "naruto", "onepiece", "gundam", "anime123",
    "ukraine", "kyiv2022", "slava123", "kohannya", "parol", "parol123",
    "паролъ", "пароль", "пароль123", "йцукен", "qwerty1234567890",
    "spring2024", "summer2024", "autumn2024", "winter2024", "spring2025",
    "summer2025", "autumn2025", "winter2025", "january2025", "december2025",
}

_COMMON_SUFFIXES = ("", "1", "12", "123", "1234", "12345", "123456", "!", "!!", "@", "#", "$",
                    "2023", "2024", "2025", "2026", "01", "007", "111")


def is_common_password(password: str) -> bool:
    lowered = password.lower().strip()
    if lowered in COMMON_PASSWORDS:
        return True
    for suffix in _COMMON_SUFFIXES:
        if suffix and lowered.endswith(suffix) and lowered[: -len(suffix)] in COMMON_PASSWORDS:
            return True
    return False


def validate_password(password: str) -> str | None:
    """Повертає текст помилки або None, якщо пароль прийнятний."""
    if len(password) < 12:
        return "Пароль має містити щонайменше 12 символів"
    if is_common_password(password):
        return "Пароль занадто поширений (знайдений у словнику витоків). Оберіть інший"
    return None
