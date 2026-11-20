import re
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import database

# ID роли рекрутеров / лидеров
DEFAULT_RECRUITER_ROLE_ID = 1372603820441468948
DEFAULT_VOICE_CHANNEL_ID = 1414100339820331039

def check_recruiter_permission(interaction: discord.Interaction) -> bool:
    settings = database.get_guild_settings(interaction.guild_id)
    recruiter_role_id = settings.get("recruiter_role_id") or DEFAULT_RECRUITER_ROLE_ID

    is_recruiter = any(r.id == recruiter_role_id for r in getattr(interaction.user, 'roles', []))
    is_admin = interaction.user.guild_permissions.administrator
    return is_recruiter or is_admin


# --- МОДАЛЬНОЕ ОКНО ПОДАЧИ ЗАЯВКИ В КЛАН ---
class ApplicationModal(discord.ui.Modal, title="Заявка в клан"):
    nickname_static = discord.ui.TextInput(
        label="ВАШ NICKNAME & СТАТИКИ (СО СТАРТЕРОМ): *",
        placeholder="Пример: Kenshi / Ваши статики на серверах со стартером",
        style=discord.TextStyle.short,
        required=True,
        max_length=150
    )
    irl_name_age = discord.ui.TextInput(
        label="ИМЯ & ВОЗРАСТ (IRL): *",
        placeholder="Пример: Рома, 18 лет",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )
    rollbacks = discord.ui.TextInput(
        label="ОТКАТЫ С ПАБГОВ / КАПТОВ: *",
        placeholder="Пример: Ссылки на откаты (YouTube, RuTube, Google Drive и т.д.)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Ошибка: заявка может быть подана только на сервере.", ephemeral=True)
            return

        settings = database.get_guild_settings(guild.id)
        if not settings.get("recruitment_open", 1):
            await interaction.response.send_message("❌ В данный момент набор в клан закрыт.", ephemeral=True)
            return

        recruiter_role_id = settings.get("recruiter_role_id") or DEFAULT_RECRUITER_ROLE_ID
        recruiter_role = guild.get_role(recruiter_role_id)

        # Сохраняем в базу данных
        app_id = database.create_application(
            guild_id=guild.id,
            user_id=interaction.user.id,
            user_tag=str(interaction.user),
            nickname_static=self.nickname_static.value,
            irl_name_age=self.irl_name_age.value,
            rollbacks=self.rollbacks.value
        )

        # Настраиваем права для нового приватного канала-тикета
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True
            )
        }

        if recruiter_role:
            overwrites[recruiter_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )

        category = interaction.channel.category if interaction.channel else None
        channel_name = f"заявка-{interaction.user.name}"
        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Заявка #{app_id} от {interaction.user} (ID: {interaction.user.id})"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка создания канала заявки: {e}", ephemeral=True)
            return

        # Создаем Embed анкеты
        embed = discord.Embed(
            title=f"📋 Заявка в клан #{app_id}",
            color=discord.Color.from_rgb(30, 31, 34),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{interaction.user.display_name} ({interaction.user})", icon_url=interaction.user.display_avatar.url)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        embed.add_field(name="👤 Кандидат", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="🎮 Nickname & Статики (со стартером)", value=f"```{self.nickname_static.value}```", inline=False)
        embed.add_field(name="🎂 Имя & Возраст (IRL)", value=f"```{self.irl_name_age.value}```", inline=True)
        embed.add_field(name="🎯 Откаты с пабгов / каптов", value=self.rollbacks.value, inline=False)
        embed.set_footer(text=f"Статус: На рассмотрении | ID заявки: {app_id} | User ID: {interaction.user.id}")

        view = ApplicationReviewView()
        tag_text = f"{interaction.user.mention} {recruiter_role.mention if recruiter_role else ''}"

        control_msg = await ticket_channel.send(
            content=f"👋 Приветствуем! {tag_text}\nЗдесь вы можете общаться с руководством по поводу вступления в клан.",
            embed=embed,
            view=view
        )

        database.set_application_review_message(app_id, control_msg.id)

        await interaction.response.send_message(
            f"✅ Ваша заявка успешно отправлена!\n"
            f"Для вас открыт приватный канал: {ticket_channel.mention}. Перейдите в него для общения с руководством.",
            ephemeral=True
        )


# --- ВЫПАДАЮЩЕЕ МЕНЮ ПОДАЧИ ЗАЯВОК ---
class RecruitmentSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Подать заявку",
                description="Открыть личный канал и заполнить анкету",
                emoji="📝",
                value="apply"
            ),
            discord.SelectOption(
                label="Статус заявки",
                description="Проверить статус вашей последней заявки",
                emoji="📊",
                value="check_status"
            )
        ]
        super().__init__(
            placeholder="Выберите действие...",
            min_values=1,
            max_values=1,
            custom_id="recruitment_main_select",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]

        if choice == "apply":
            settings = database.get_guild_settings(interaction.guild_id)
            if not settings.get("recruitment_open", 1):
                await interaction.response.send_message("🔴 В данный момент набор в клан закрыт.", ephemeral=True)
                return
            await interaction.response.send_modal(ApplicationModal())

        elif choice == "check_status":
            app = database.get_user_last_application(interaction.guild_id, interaction.user.id)
            if not app:
                await interaction.response.send_message("ℹ️ Вы ещё не подавали заявок в клан.", ephemeral=True)
                return

            status_map = {
                "pending": "🟡 На рассмотрении",
                "accepted": "🟢 Одобрена",
                "rejected": "🔴 Отклонена",
                "interview": "📞 Приглашение на обзвон"
            }
            status_text = status_map.get(app["status"], app["status"])
            msg = f"📌 **Ваша последняя заявка (#{app['id']})**\nСтатус: **{status_text}**\nПодана: `{app['created_at']}`"
            if app["status"] == "rejected" and app["reject_reason"]:
                msg += f"\nПричина: *{app['reject_reason']}*"
            await interaction.response.send_message(msg, ephemeral=True)


class RecruitmentMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RecruitmentSelect())


# --- МОДАЛЬНОЕ ОКНО ДЛЯ ОТКЛОНЕНИЯ ЗАЯВКИ С ПРИЧИНОЙ ---
class RejectReasonModal(discord.ui.Modal, title="Отклонение заявки"):
    reason = discord.ui.TextInput(
        label="Причина отказа:",
        placeholder="Укажите причину (слабые откаты, чс, неадекватность и т.д.)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, app_id: int, applicant_id: int, review_message: discord.Message):
        super().__init__()
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.review_message = review_message

    async def on_submit(self, interaction: discord.Interaction):
        database.update_application_status(self.app_id, "rejected", self.reason.value)

        # Отправляем уведомление кандидату в ЛС
        applicant = interaction.guild.get_member(self.applicant_id)
        if applicant:
            try:
                dm_embed = discord.Embed(
                    title="Уведомление о заявке в клан",
                    description=f"К сожалению, ваша заявка в клан была **отклонена**.\n\n**Причина:** {self.reason.value}",
                    color=discord.Color.red()
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"🔴 **Заявка #{self.app_id} отклонена.**\n"
            f"Причина: *{self.reason.value}*\n"
            f"🔒 Канал закроется и удалится через 5 секунд...",
        )

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


def extract_app_and_user_id(message: discord.Message):
    if not message.embeds:
        return None, None
    footer = message.embeds[0].footer.text or ""
    app_match = re.search(r"ID заявки:\s*(\d+)", footer)
    user_match = re.search(r"User ID:\s*(\d+)", footer)
    app_id = int(app_match.group(1)) if app_match else None
    user_id = int(user_match.group(1)) if user_match else None
    return app_id, user_id


# --- ПАНЕЛЬ УПРАВЛЕНИЯ ЗАЯВКОЙ В ПРИВАТНОМ КАНАЛЕ ---
class ApplicationReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, emoji="✅", custom_id="app_btn_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = database.get_guild_settings(interaction.guild_id)
        recruiter_role_id = settings.get("recruiter_role_id") or DEFAULT_RECRUITER_ROLE_ID

        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Управлять заявкой может только роль <@&{recruiter_role_id}>.", ephemeral=True)
            return

        app_id, applicant_id = extract_app_and_user_id(interaction.message)
        if not app_id:
            await interaction.response.send_message("❌ Не удалось определить ID заявки.", ephemeral=True)
            return

        database.update_application_status(app_id, "accepted")

        # Выдаем роль если настроена
        member_role_id = settings.get("member_role_id")
        applicant = interaction.guild.get_member(applicant_id) if applicant_id else None
        role_added = False
        if applicant and member_role_id:
            role = interaction.guild.get_role(member_role_id)
            if role:
                try:
                    await applicant.add_roles(role)
                    role_added = True
                except discord.Forbidden:
                    pass

        # Отправляем поздравление в ЛС
        if applicant:
            try:
                dm_embed = discord.Embed(
                    title="🎉 Поздравляем! Заявка одобрена",
                    description=f"Ваша заявка в клан **{settings.get('clan_name', '116 clnx')}** была успешно **одобрена**!\nДобро пожаловать в клан!",
                    color=discord.Color.green()
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        res = f"✅ **Заявка #{app_id} одобрена!**"
        if role_added:
            res += " Роль участника успешно выдана."
        res += "\n🔒 Канал заявки будет удалён через 5 секунд..."

        await interaction.response.send_message(res)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="На обзвон", style=discord.ButtonStyle.primary, emoji="📞", custom_id="app_btn_interview")
    async def interview(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = database.get_guild_settings(interaction.guild_id)
        recruiter_role_id = settings.get("recruiter_role_id") or DEFAULT_RECRUITER_ROLE_ID

        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Управлять заявкой может только роль <@&{recruiter_role_id}>.", ephemeral=True)
            return

        app_id, applicant_id = extract_app_and_user_id(interaction.message)
        if not app_id:
            await interaction.response.send_message("❌ Не удалось определить ID заявки.", ephemeral=True)
            return

        database.update_application_status(app_id, "interview")

        # Обновляем эмбед в канале тикета, кнопки НЕ удаляем
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.blue()
        embed.set_footer(text=f"Статус: 📞 Вызван на обзвон ({interaction.user.display_name}) | ID заявки: {app_id} | User ID: {applicant_id}")
        await interaction.message.edit(embed=embed, view=self)

        applicant = interaction.guild.get_member(applicant_id) if applicant_id else None
        voice_channel_id = settings.get("voice_channel_id") or DEFAULT_VOICE_CHANNEL_ID
        voice_url = f"https://discord.com/channels/{interaction.guild_id}/{voice_channel_id}"

        # Пишем прямо в приватный канал тикета с тегом кандидата
        ticket_invite = (
            f"📞 **Внимание, {applicant.mention if applicant else 'кандидат'}!**\n"
            f"Руководство клана вызывает вас на обзвон.\n"
            f"🎙️ **Голосовой канал:** <#{voice_channel_id}>\n"
            f"Пожалуйста, зайдите в голосовой канал и ожидайте рекрутера."
        )
        await interaction.channel.send(ticket_invite)

        # Дублируем кандидату в ЛС
        if applicant:
            try:
                dm_embed = discord.Embed(
                    title="📞 Приглашение на обзвон",
                    description=(
                        f"Здравствуйте! Руководство клана **{settings.get('clan_name', '116 clnx')}** приглашает вас на обзвон.\n\n"
                        f"🎙️ **Перейдите в голосовой канал:** <#{voice_channel_id}>\n"
                        f"Прямая ссылка: {voice_url}\n\n"
                        f"Ожидайте рекрутера в канале."
                    ),
                    color=discord.Color.blue()
                )
                dm_view = discord.ui.View()
                dm_view.add_item(discord.ui.Button(label="Войти в голосовой канал", url=voice_url, style=discord.ButtonStyle.link, emoji="🎙️"))
                await applicant.send(embed=dm_embed, view=dm_view)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"✅ Кандидат вызван на обзвон!\n"
            f"Ссылка на голосовой канал (<#{voice_channel_id}>) продублирована в этот чат и в ЛС кандидату.\n"
            f"После обзвона нажмите «Принять» или «Отклонить» для закрытия заявки.",
            ephemeral=True
        )

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="app_btn_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = database.get_guild_settings(interaction.guild_id)
        recruiter_role_id = settings.get("recruiter_role_id") or DEFAULT_RECRUITER_ROLE_ID

        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Управлять заявкой может только роль <@&{recruiter_role_id}>.", ephemeral=True)
            return

        app_id, applicant_id = extract_app_and_user_id(interaction.message)
        if not app_id:
            await interaction.response.send_message("❌ Не удалось определить ID заявки.", ephemeral=True)
            return

        await interaction.response.send_modal(RejectReasonModal(app_id, applicant_id, interaction.message))

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="app_btn_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = database.get_guild_settings(interaction.guild_id)
        recruiter_role_id = settings.get("recruiter_role_id") or DEFAULT_RECRUITER_ROLE_ID

        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Закрыть тикет может только роль <@&{recruiter_role_id}>.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 **Тикет закрывается...** Канал будет удалён через 3 секунды.")
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


# --- КОГ РЕКРУТИНГА СО СЛЭШ-КОМАНДАМИ ---
class RecruitmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_recruitment", description="Настройка роли рекрутеров, войса и параметров клана")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        recruiter_role="Роль тех, кто может рассматривать заявки (по умолчанию 1372603820441468948)",
        voice_channel="Голосовой канал для обзвона (по умолчанию 1414100339820331039)",
        clan_name="Название клана (по умолчанию 116 clnx)",
        member_role="Роль, которая выдается при одобрении заявки",
        banner_photo="Фото-баннер для шапки меню (можно прикрепить файл прямо сюда)",
        banner_url="Или ссылка на фото-баннер"
    )
    async def setup_recruitment(
        self,
        interaction: discord.Interaction,
        recruiter_role: discord.Role = None,
        voice_channel: discord.VoiceChannel = None,
        clan_name: str = "116 clnx",
        member_role: discord.Role = None,
        banner_photo: discord.Attachment = None,
        banner_url: str = ""
    ):
        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Эта команда доступна только для роли <@&{DEFAULT_RECRUITER_ROLE_ID}>.", ephemeral=True)
            return

        chosen_banner = banner_photo.url if banner_photo else banner_url
        rec_role_id = recruiter_role.id if recruiter_role else DEFAULT_RECRUITER_ROLE_ID
        voice_id = voice_channel.id if voice_channel else DEFAULT_VOICE_CHANNEL_ID

        database.update_guild_settings(
            interaction.guild_id,
            clan_name=clan_name,
            voice_channel_id=voice_id,
            member_role_id=member_role.id if member_role else None,
            recruiter_role_id=rec_role_id,
            banner_url=chosen_banner
        )
        await interaction.response.send_message(
            f"✅ **Настройки клана успешно сохранены!**\n"
            f"• Название клана: **{clan_name}**\n"
            f"• Роль рекрутера: <@&{rec_role_id}>\n"
            f"• Голосовой канал для обзвона: <#{voice_id}>\n"
            f"• Роль участника: {member_role.mention if member_role else 'Не задана'}\n"
            f"• Баннер: {'Прикреплен' if chosen_banner else 'Не задан'}",
            ephemeral=True
        )

    @app_commands.command(name="post_recruitment_menu", description="Отправить красивое меню подачи заявок в клан")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        channel="Канал, куда отправить меню (по умолчанию текущий)",
        banner_photo="Прикрепите фото для баннера прямо к команде",
        banner_url="Или укажите прямую ссылку на фото-баннер"
    )
    async def post_recruitment_menu(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        banner_photo: discord.Attachment = None,
        banner_url: str = ""
    ):
        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Эта команда доступна только для роли <@&{DEFAULT_RECRUITER_ROLE_ID}>.", ephemeral=True)
            return

        target_channel = channel or interaction.channel
        settings = database.get_guild_settings(interaction.guild_id)

        clan = settings.get("clan_name", "116 clnx")
        is_open = settings.get("recruitment_open", 1)
        status_text = "🟢 Открыт набор" if is_open else "🔴 Набор закрыт"

        embed = discord.Embed(
            title=f"🖐️ Заявка в клан {clan}",
            color=discord.Color.from_rgb(30, 31, 34)
        )

        desc = (
            f"• Уведомление о приглашении на обзвон отправляется в закрытый канал, видимый только Вам и рекрутам.\n"
            f"• Если нет функциональной возможности оставить заявку — набор временно приостановлен.\n"
            f"• В данный момент статус набора: {status_text}\n\n"
            f"📑 **Основные требования для вступления:**\n"
            f"```[1] Желание играть пабги.```"
        )
        embed.description = desc

        chosen_banner = banner_photo.url if banner_photo else (banner_url or settings.get("banner_url"))
        if chosen_banner:
            embed.set_image(url=chosen_banner)
            if banner_photo or banner_url:
                database.update_guild_settings(interaction.guild_id, banner_url=chosen_banner)

        view = RecruitmentMenuView()
        await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Меню подачи заявок отправлено в {target_channel.mention}!", ephemeral=True)

    @app_commands.command(name="recruitment_toggle", description="Открыть или закрыть приём заявок в клан")
    @app_commands.default_permissions(administrator=True)
    async def recruitment_toggle(self, interaction: discord.Interaction, open_status: bool):
        if not check_recruiter_permission(interaction):
            await interaction.response.send_message(f"❌ Эта команда доступна только для роли <@&{DEFAULT_RECRUITER_ROLE_ID}>.", ephemeral=True)
            return

        database.update_guild_settings(interaction.guild_id, recruitment_open=1 if open_status else 0)
        status = "🟢 открыт" if open_status else "🔴 закрыт"
        await interaction.response.send_message(f"✅ Статус набора изменён: набор в клан теперь **{status}**.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RecruitmentCog(bot))
