import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

import database
from cogs.recruitment import RecruitmentMenuView, ApplicationReviewView
from cogs.pubg import PubgEventView
from web_panel import create_web_app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ClanBot")

# Загрузка переменных окружения из .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("WEB_PORT", 5000))

# Настройка интентов бота
intents = discord.Intents.default()
intents.members = True          # Для работы с ролями и участниками
intents.message_content = True  # Для сообщений

class ClanBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.web_runner = None

    async def setup_hook(self):
        # 1. Инициализируем базу данных SQLite
        database.init_db()
        logger.info("База данных успешно инициализирована.")

        # 2. Регистрируем постоянные View (кнопки и селекты продолжат работать после перезапуска)
        self.add_view(RecruitmentMenuView())
        self.add_view(ApplicationReviewView())
        self.add_view(PubgEventView())
        logger.info("Постоянные View зарегистрированы.")

        # 3. Загружаем коги
        for cog_name in ["cogs.recruitment", "cogs.pubg"]:
            try:
                await self.load_extension(cog_name)
                logger.info(f"Ког {cog_name} успешно загружен.")
            except Exception as e:
                logger.error(f"Не удалось загрузить {cog_name}: {e}", exc_info=True)

        # 4. Запускаем локальную веб-панель управления
        try:
            web_app = create_web_app()
            self.web_runner = web.AppRunner(web_app)
            await self.web_runner.setup()
            site = web.TCPSite(self.web_runner, "0.0.0.0", PORT)
            await site.start()
            logger.info(f"🌐 Веб-панель управления запущена по адресу: http://localhost:{PORT}")
        except Exception as e:
            logger.warning(f"Не удалось запустить веб-панель на порту {PORT}: {e}")

    async def close(self):
        if self.web_runner:
            await self.web_runner.cleanup()
        await super().close()

    async def on_ready(self):
        logger.info(f"Бот успешно запущен под именем: {self.user} (ID: {self.user.id})")
        # Удаляем дубли и синхронизируем единый список команд
        try:
            for guild in self.guilds:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            synced = await self.tree.sync()
            logger.info(f"Синхронизировано уникальных команд: {len(synced)} (дубликаты очищены)")
        except Exception as e:
            logger.error(f"Ошибка при синхронизации команд: {e}")

        # Установка статуса бота
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="116 clnx | /pubg"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)


async def main():
    if not TOKEN or TOKEN == "your_bot_token_here":
        print("\n" + "="*60)
        print("ВНИМАНИЕ: Не указан токен бота в файле .env!")
        print("Откройте файл .env и вставьте ваш токен в строку:")
        print("DISCORD_TOKEN=ваш_токен_здесь")
        print("="*60 + "\n")
        return

    bot = ClanBot()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
