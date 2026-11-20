import discord
from discord.ext import commands
from discord import app_commands
import database

# Настройки доступа для создания сборов PUBG
PUBG_CHANNEL_ID = 1454583147659264031
PUBG_ALLOWED_ROLE_IDS = {1372603820441468948, 1372601026992934912}

def can_create_pubg(interaction: discord.Interaction) -> bool:
    user_roles = {r.id for r in getattr(interaction.user, 'roles', [])}
    is_admin = interaction.user.guild_permissions.administrator
    return bool(user_roles & PUBG_ALLOWED_ROLE_IDS) or is_admin

# Хелпер для форматирования Embed мероприятия
def format_event_embed(event: dict, participants: list, banner_url: str = None) -> discord.Embed:
    is_closed = event.get("is_closed", 0)
    status_prefix = "🔒 [РЕГИСТРАЦИЯ ЗАКРЫТА] " if is_closed else "🏆 "
    team_name = event.get("team_name") or "116w 2x2"

    # Черная / темная полоска
    embed_color = discord.Color.from_rgb(20, 20, 20) if not is_closed else discord.Color.red()

    embed = discord.Embed(
        title=f"{status_prefix}РЕГИСТРАЦИЯ НА МЕРОПРИЯТИЕ: PUBG",
        description="Внимание состав! Открыта запись на турнир/мероприятие по **PUBG**.\nНажмите кнопку **«Кинуть +»** ниже и введите свой статический ID.",
        color=embed_color,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(name="👥 Команда + огран:", value=f"```{team_name}```", inline=True)
    embed.add_field(name="🌐 Сервер проведения:", value=f"```{event['game_server']}```", inline=True)
    embed.add_field(name="⏰ Дата и время МП:", value=f"```{event['event_time']}```", inline=True)
    embed.add_field(name="⏳ Начало регистрации:", value=f"```{event['reg_deadline']}```", inline=True)

    if event.get("notes"):
        embed.add_field(name="ℹ️ Дополнительная информация:", value=event["notes"], inline=False)

    organizer_mention = f"<@{event['organizer_id']}>" if event.get("organizer_id") else "Руководство"
    embed.add_field(name="👑 Организатор:", value=organizer_mention, inline=True)

    count = len(participants)
    confirmed_count = sum(1 for p in participants if dict(p).get("is_confirmed", 0))
    embed.add_field(name="👥 Всего записалось:", value=f"**{count} чел.** (Вписано: {confirmed_count})", inline=True)

    # Список участников (с галочкой ✅ после тега, если вписан организатором)
    if participants:
        lines = []
        for idx, p in enumerate(participants, 1):
            check_mark = " ✅" if dict(p).get("is_confirmed", 0) else ""
            lines.append(f"`{idx}.` <@{p['user_id']}>{check_mark} — Статик: **{p['static_id']}**")

        text = "\n".join(lines)
        if len(text) > 1020:
            text = text[:1000] + "\n... и другие"
        embed.add_field(name="📋 Список состава (+):", value=text, inline=False)
    else:
        embed.add_field(name="📋 Список состава (+):", value="*Пока никто не кинул плюс. Будь первым!*", inline=False)

    # Установка баннера клана
    if banner_url and banner_url.startswith("http"):
        embed.set_image(url=banner_url)

    embed.set_footer(text="116 clnx • PUBG Tournament")
    return embed


# --- ВЫПАДАЮЩИЙ СПИСОК ДЛЯ ОРГАНИЗАТОРА (ВПИСАТЬ УЧАСТНИКА С ГАЛОЧКОЙ) ---
class PubgConfirmSelect(discord.ui.Select):
    def __init__(self, event: dict, participants: list, original_message: discord.Message):
        self.event = event
        self.participants = participants
        self.original_message = original_message

        options = []
        for p in participants[:25]:
            is_conf = dict(p).get("is_confirmed", 0)
            status_text = "Уже вписан ✅" if is_conf else "Не вписан"
            options.append(discord.SelectOption(
                label=f"{p['user_name'][:25]}",
                description=f"Статик: {p['static_id']} | {status_text}",
                emoji="✅" if is_conf else "⚪",
                value=str(p["user_id"])
            ))

        super().__init__(
            placeholder="Выберите игрока, чтобы поставить/снять галочку ✅...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # Только создатель этого сбора может вписывать
        if interaction.user.id != self.event.get("organizer_id"):
            await interaction.response.send_message(
                f"❌ Отмечать участников может только организатор этого сбора (<@{self.event.get('organizer_id')}>)!",
                ephemeral=True
            )
            return

        target_user_id = int(self.values[0])
        new_status = database.toggle_participant_confirmed(self.event["id"], target_user_id)

        # Обновляем эмбед сообщения сбора
        settings = database.get_guild_settings(interaction.guild_id)
        pubg_banner = settings.get("pubg_banner_url")

        updated_parts = database.get_event_participants(self.event["id"])
        new_embed = format_event_embed(self.event, updated_parts, pubg_banner)

        try:
            await self.original_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Ошибка обновления эмбеда: {e}")

        status_msg = "вписан с галочкой ✅" if new_status else "снят с отметки"
        await interaction.response.send_message(
            f"✅ Игрок <@{target_user_id}> теперь **{status_msg}** в списке!",
            ephemeral=True
        )


class PubgConfirmView(discord.ui.View):
    def __init__(self, event: dict, participants: list, original_message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(PubgConfirmSelect(event, participants, original_message))


# --- МОДАЛКА ВВОДА СТАТИКА ПРИ КИДАНИИ ПЛЮСА ---
class PubgJoinModal(discord.ui.Modal, title="Регистрация на PUBG"):
    static_id = discord.ui.TextInput(
        label="ВАШ СТАТИЧЕСКИЙ ID И НИК: *",
        placeholder="Пример: 5768 | Mirwana",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )

    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        event = database.get_event_by_message(self.message_id)
        if not event:
            await interaction.response.send_message("❌ Мероприятие не найдено в базе данных.", ephemeral=True)
            return

        if event.get("is_closed", 0):
            await interaction.response.send_message("🔒 Регистрация на это мероприятие уже завершена!", ephemeral=True)
            return

        team_name = event.get("team_name") or "116w 2x2"

        # Добавляем или обновляем участника
        database.add_event_participant(
            event_id=event["id"],
            user_id=interaction.user.id,
            user_name=str(interaction.user),
            static_id=self.static_id.value,
            team_name=team_name
        )

        # Отправляем сообщение в ветку обсуждения с тегом
        thread = None
        message = interaction.message
        if message:
            try:
                if message.thread:
                    thread = message.thread
                else:
                    thread = await message.create_thread(name=f"PUBG {event['game_server']} | {team_name}")
                    database.update_event_thread(event["id"], thread.id)

                if thread:
                    thread_embed = discord.Embed(
                        description=(
                            f"➕ {interaction.user.mention} кинул(а) плюс на PUBG!\n\n"
                            f"🎮 **Ник и статик:** `{self.static_id.value}`\n"
                            f"👥 **Команда:** `{team_name}`"
                        ),
                        color=discord.Color.from_rgb(30, 31, 34)
                    )
                    await thread.send(content=interaction.user.mention, embed=thread_embed)
            except Exception as e:
                print(f"Ошибка отправки сообщения в ветку: {e}")

        # Обновляем главное сообщение мероприятия
        settings = database.get_guild_settings(interaction.guild_id)
        pubg_banner = settings.get("pubg_banner_url")

        participants = database.get_event_participants(event["id"])
        new_embed = format_event_embed(event, participants, pubg_banner)

        try:
            await interaction.message.edit(embed=new_embed)
        except Exception as e:
            print(f"Ошибка обновления эмбеда: {e}")

        await interaction.response.send_message(
            f"✅ **Вы успешно записались на PUBG!**\n"
            f"• Команда: `{team_name}`\n"
            f"• Статик: `{self.static_id.value}`\n"
            f"Информация продублирована в ветку сбора.",
            ephemeral=True
        )


# --- КНОПКИ УПРАВЛЕНИЯ ЗАПИСЬЮ (ПЛЮС, ОТМЕНА, ВПИСАТЬ, ЗАКРЫТИЕ) ---
class PubgEventView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Кинуть +", style=discord.ButtonStyle.success, emoji="➕", custom_id="pubg_btn_plus")
    async def join_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        event = database.get_event_by_message(interaction.message.id)
        if not event:
            await interaction.response.send_message("❌ Данные мероприятия не найдены.", ephemeral=True)
            return

        if event.get("is_closed", 0):
            await interaction.response.send_message("🔒 Регистрация закрыта организатором.", ephemeral=True)
            return

        await interaction.response.send_modal(PubgJoinModal(message_id=interaction.message.id))

    @discord.ui.button(label="Отменить запись", style=discord.ButtonStyle.secondary, emoji="➖", custom_id="pubg_btn_leave")
    async def leave_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        event = database.get_event_by_message(interaction.message.id)
        if not event:
            await interaction.response.send_message("❌ Мероприятие не найдено.", ephemeral=True)
            return

        deleted = database.remove_event_participant(event["id"], interaction.user.id)
        if not deleted:
            await interaction.response.send_message("ℹ️ Вы не были записаны в списке участников.", ephemeral=True)
            return

        settings = database.get_guild_settings(interaction.guild_id)
        pubg_banner = settings.get("pubg_banner_url")

        participants = database.get_event_participants(event["id"])
        new_embed = format_event_embed(event, participants, pubg_banner)
        await interaction.message.edit(embed=new_embed)

        if interaction.message.thread:
            try:
                await interaction.message.thread.send(f"➖ {interaction.user.mention} отменил(а) свою запись на PUBG.")
            except Exception:
                pass

        await interaction.response.send_message("❌ Вы удалили себя из списка участников мероприятия.", ephemeral=True)

    @discord.ui.button(label="Вписать", style=discord.ButtonStyle.primary, emoji="📝", custom_id="pubg_btn_confirm")
    async def confirm_participant(self, interaction: discord.Interaction, button: discord.ui.Button):
        event = database.get_event_by_message(interaction.message.id)
        if not event:
            await interaction.response.send_message("❌ Мероприятие не найдено.", ephemeral=True)
            return

        # СТРОГО: управлять сбором может ТОЛЬКО тот, кто его создал
        if interaction.user.id != event.get("organizer_id"):
            organizer_tag = f"<@{event.get('organizer_id')}>" if event.get("organizer_id") else "организатор"
            await interaction.response.send_message(
                f"❌ Это чужой сбор! Управлять списком участников может только его создатель ({organizer_tag}).",
                ephemeral=True
            )
            return

        participants = database.get_event_participants(event["id"])
        if not participants:
            await interaction.response.send_message("ℹ️ В списке участников пока никого нет.", ephemeral=True)
            return

        # Отправляем меню выбора участника
        view = PubgConfirmView(event, participants, interaction.message)
        await interaction.response.send_message("Выберите игрока из списка, чтобы поставить или снять галочку ✅:", view=view, ephemeral=True)

    @discord.ui.button(label="Завершить регистрацию", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="pubg_btn_close")
    async def close_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        event = database.get_event_by_message(interaction.message.id)
        if not event:
            await interaction.response.send_message("❌ Мероприятие не найдено.", ephemeral=True)
            return

        # СТРОГО: закрыть сбор может ТОЛЬКО тот, кто его создал
        if interaction.user.id != event.get("organizer_id"):
            organizer_tag = f"<@{event.get('organizer_id')}>" if event.get("organizer_id") else "организатор"
            await interaction.response.send_message(
                f"❌ Это чужой сбор! Завершить регистрацию может только его создатель ({organizer_tag}).",
                ephemeral=True
            )
            return

        database.close_event(event["id"])
        event["is_closed"] = 1

        settings = database.get_guild_settings(interaction.guild_id)
        pubg_banner = settings.get("pubg_banner_url")

        participants = database.get_event_participants(event["id"])
        new_embed = format_event_embed(event, participants, pubg_banner)

        self.stop()
        await interaction.message.edit(embed=new_embed, view=None)

        if interaction.message.thread:
            try:
                await interaction.message.thread.send("🔒 **Регистрация на PUBG официально закрыта организатором.**")
            except Exception:
                pass

        await interaction.response.send_message("🔒 Регистрация успешно закрыта!", ephemeral=True)


# --- КОГ PUBG С КОМАНДОЙ /pubg ---
class PubgCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="pubg",
        description="Создать сбор и регистрацию на PUBG с тегом @everyone"
    )
    @app_commands.describe(
        команда_огран="Название команды и ограничение (например, 116w 2x2)",
        сервер="Сервер проведения мероприятия (например, 02 или Boston)",
        время_мп="Дата и время начала МП (например, 21.11 в 21:00)",
        начало_реги="Время начала регистрации (например, 15:00)",
        дополнительно="Примечания, правила или информация о спецсвязи (необязательно)",
        баннер="Прикрепите фото-баннер для шапки турнира (необязательно)"
    )
    async def pubg(
        self,
        interaction: discord.Interaction,
        команда_огран: str,
        сервер: str,
        время_мп: str,
        начало_реги: str,
        дополнительно: str = "",
        баннер: discord.Attachment = None
    ):
        # 1. Проверка канала: писать /pubg можно ТОЛЬКО в 1454583147659264031
        if interaction.channel_id != PUBG_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ Команду `/pubg` можно использовать только в канале <#{PUBG_CHANNEL_ID}>!",
                ephemeral=True
            )
            return

        # 2. Проверка ролей: только 1372603820441468948 и 1372601026992934912
        if not can_create_pubg(interaction):
            await interaction.response.send_message(
                "❌ Запускать сбор на PUBG могут только роли <@&1372603820441468948> и <@&1372601026992934912>.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        settings = database.get_guild_settings(interaction.guild_id)
        pubg_banner = баннер.url if баннер else settings.get("pubg_banner_url")

        if баннер:
            database.update_guild_settings(interaction.guild_id, pubg_banner_url=баннер.url)

        event_dummy = {
            "team_name": команда_огран,
            "game_server": сервер,
            "event_time": время_мп,
            "reg_deadline": начало_реги,
            "notes": дополнительно,
            "organizer_id": interaction.user.id,
            "is_closed": 0
        }
        initial_embed = format_event_embed(event_dummy, [], pubg_banner)
        view = PubgEventView()

        msg = await interaction.channel.send(
            content="@everyone",
            embed=initial_embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )

        # Создаем ветку сразу при публикации сбора
        thread = None
        try:
            thread = await msg.create_thread(name=f"PUBG {сервер} | {команда_огран}")
            await thread.send(f"📌 Ветка сбора **{команда_огран}** на PUBG. При нажатии «Кинуть +» информация об участниках будет появляться здесь.")
        except Exception as e:
            print(f"Не удалось создать ветку: {e}")

        # Сохраняем в БД
        database.create_event(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            message_id=msg.id,
            team_name=команда_огран,
            game_server=сервер,
            event_time=время_мп,
            reg_deadline=начало_реги,
            notes=дополнительно,
            organizer_id=interaction.user.id,
            thread_id=thread.id if thread else None
        )

        await interaction.followup.send(f"✅ Регистрация команды **{команда_огран}** на PUBG успешно опубликована в {interaction.channel.mention}!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PubgCog(bot))
