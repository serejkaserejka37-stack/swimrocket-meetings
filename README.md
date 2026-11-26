# SwimRocket Встречи

Приложение для автоматической записи Zoom и Яндекс Телемост, серверной расшифровки и разбора встреч. Работает на Windows и macOS; Whisper и Gemini выполняются на сервере, а не на компьютере.

## Скачать

Перейдите в [Releases](https://github.com/serejkaserejka37-stack/swimrocket-meetings/releases):

- **Windows:** `SwimRocketMeetings-Setup.exe`.
- **MacBook:** `SwimRocketMeetings.dmg` — выберите сборку для вашего процессора.
- [Инструкция Windows](docs/SwimRocket-Инструкция-Windows.pdf).
- [Инструкция macOS](docs/SwimRocket-Инструкция-macOS.pdf).

## Первичная настройка

1. Установите и откройте приложение.
2. В мастере нажмите «Начать настройку».
3. Откройте [@swimrocket_meetings_bot](https://t.me/swimrocket_meetings_bot) и нажмите **Start**.
4. Введите в приложение одноразовый код из бота.
5. Дождитесь подтверждения и сделайте короткую тестовую запись.

Каждый пользователь получает собственный токен и сводки только в свой Telegram. SSH и Obsidian не используются. Для записи звука собеседников на MacBook нужен BlackHole.

## Основные возможности

- автоматическое обнаружение окна конференции;
- запись микрофона и системного звука;
- серверная расшифровка, тезисы, решения и задачи;
- доставка в привязанный Telegram с проверкой и повтором;
- локальное хранение результатов;
- светлый фирменный интерфейс SwimRocket.

## Сборка

- Windows: `packaging/build_windows.ps1`.
- macOS: `bash packaging/build_macos.sh`.
- Обе платформы также собираются в GitHub Actions.

Проект основан на [TalkTrack](https://github.com/ObscureAintSecure/TalkTrack) (MIT). См. `LICENSE` и `CREDITS.md`.
