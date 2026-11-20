import os
from aiohttp import web
import database

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Панель управления кланом 116 clnx</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #111214;
            --card-bg: #1e1f22;
            --input-bg: #2b2d31;
            --border-color: #35373c;
            --accent: #5865F2;
            --accent-hover: #4752c4;
            --text-main: #f2f3f5;
            --text-muted: #949ba4;
            --green: #23a55a;
            --red: #f23f43;
            --yellow: #f0b232;
            --blue: #00a8fc;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            padding: 30px 20px;
            display: flex;
            justify-content: center;
        }

        .container {
            max-width: 1100px;
            width: 100%;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }

        .logo-area h1 {
            font-size: 26px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .badge-online {
            background-color: rgba(35, 165, 90, 0.2);
            color: var(--green);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }

        .tabs {
            display: flex;
            gap: 12px;
            margin-bottom: 25px;
        }

        .tab-btn {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .tab-btn.active, .tab-btn:hover {
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }

        .panel-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 25px;
        }

        .panel-card h2 {
            font-size: 18px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 18px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        input[type="text"], input[type="number"], select {
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 12px 14px;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }

        input:focus, select:focus {
            border-color: var(--accent);
        }

        .toggle-group {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 10px;
        }

        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 48px;
            height: 26px;
        }

        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: var(--input-bg);
            transition: .3s;
            border-radius: 34px;
            border: 1px solid var(--border-color);
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .3s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--green);
            border-color: var(--green);
        }

        input:checked + .slider:before {
            transform: translateX(22px);
        }

        .save-btn {
            background: var(--accent);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
            transition: background 0.2s;
        }

        .save-btn:hover {
            background: var(--accent-hover);
        }

        .table-responsive {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }

        th {
            background: var(--input-bg);
            color: var(--text-muted);
            padding: 12px;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            vertical-align: top;
        }

        tr:hover {
            background: rgba(255, 255, 255, 0.02);
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge-pending { background: rgba(240, 178, 50, 0.2); color: var(--yellow); }
        .badge-accepted { background: rgba(35, 165, 90, 0.2); color: var(--green); }
        .badge-rejected { background: rgba(242, 63, 67, 0.2); color: var(--red); }
        .badge-interview { background: rgba(0, 168, 252, 0.2); color: var(--blue); }

        .notify {
            display: none;
            padding: 12px;
            background: var(--green);
            color: white;
            border-radius: 8px;
            margin-bottom: 15px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-area">
                <h1>🎮 116 clnx • Панель управления</h1>
                <p style="color: var(--text-muted); margin-top: 4px;">Управление набором, заявками в клан и турнирами PUBG</p>
            </div>
            <div>
                <span class="badge-online">● Бот активен</span>
            </div>
        </header>

        <div id="notify" class="notify">Настройки успешно сохранены!</div>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('settings')">⚙️ Настройки клана</button>
            <button class="tab-btn" onclick="switchTab('apps')">📋 Заявки в клан</button>
            <button class="tab-btn" onclick="switchTab('pubg')">🏆 Мероприятия (PUBG)</button>
        </div>

        <!-- ВКЛАДКА НАСТРОЙКИ -->
        <div id="tab-settings" class="tab-content">
            <div class="panel-card">
                <h2>⚙️ Основные параметры клана</h2>
                <form id="settingsForm" onsubmit="saveSettings(event)">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Название клана</label>
                            <input type="text" id="clan_name" name="clan_name" value="{{clan_name}}">
                        </div>
                        <div class="form-group">
                            <label>ID приватного канала для заявок</label>
                            <input type="text" id="review_channel_id" name="review_channel_id" value="{{review_channel_id}}" placeholder="ID канала (куда слать заявки)">
                        </div>
                        <div class="form-group">
                            <label>ID голосового канала для обзвона</label>
                            <input type="text" id="voice_channel_id" name="voice_channel_id" value="{{voice_channel_id}}" placeholder="1414100339820331039">
                        </div>
                        <div class="form-group">
                            <label>ID роли рекрутера / лидера</label>
                            <input type="text" id="recruiter_role_id" name="recruiter_role_id" value="{{recruiter_role_id}}" placeholder="ID роли">
                        </div>
                        <div class="form-group">
                            <label>ID роли участника (выдается при одобрении)</label>
                            <input type="text" id="member_role_id" name="member_role_id" value="{{member_role_id}}" placeholder="ID роли">
                        </div>
                        <div class="form-group">
                            <label>Баннер меню заявок (URL фото)</label>
                            <input type="text" id="banner_url" name="banner_url" value="{{banner_url}}" placeholder="https://...">
                        </div>
                        <div class="form-group">
                            <label>Баннер логотипа клана для PUBG (URL фото)</label>
                            <input type="text" id="pubg_banner_url" name="pubg_banner_url" value="{{pubg_banner_url}}" placeholder="https://...">
                        </div>
                    </div>

                    <div class="form-group" style="margin-top: 20px;">
                        <label>Статус набора в клан</label>
                        <div class="toggle-group">
                            <label class="toggle-switch">
                                <input type="checkbox" id="recruitment_open" name="recruitment_open" {{recruitment_checked}}>
                                <span class="slider"></span>
                            </label>
                            <span id="recruitment_label" style="font-weight: 600;">{{recruitment_text}}</span>
                        </div>
                    </div>

                    <button type="submit" class="save-btn">💾 Сохранить изменения</button>
                </form>
            </div>
        </div>

        <!-- ВКЛАДКА ЗАЯВКИ -->
        <div id="tab-apps" class="tab-content" style="display: none;">
            <div class="panel-card">
                <h2>📋 Поступившие анкеты ({{apps_count}})</h2>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Кандидат</th>
                                <th>Ник & Статики (со стартером)</th>
                                <th>Имя & Возраст</th>
                                <th>Откаты с пабгов / каптов</th>
                                <th>Статус</th>
                            </tr>
                        </thead>
                        <tbody>
                            {{apps_rows}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ВКЛАДКА PUBG -->
        <div id="tab-pubg" class="tab-content" style="display: none;">
            <div class="panel-card">
                <h2>🏆 Мероприятия и турниры</h2>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Сервер</th>
                                <th>Время проведения</th>
                                <th>Конец регистрации</th>
                                <th>Участники & Команды</th>
                                <th>Статус</th>
                            </tr>
                        </thead>
                        <tbody>
                            {{pubg_rows}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        function switchTab(name) {
            document.querySelectorAll('.tab-content').forEach(function(el) { el.style.display = 'none'; });
            document.querySelectorAll('.tab-btn').forEach(function(el) { el.classList.remove('active'); });
            document.getElementById('tab-' + name).style.display = 'block';
            event.target.classList.add('active');
        }

        var checkbox = document.getElementById('recruitment_open');
        var label = document.getElementById('recruitment_label');
        if (checkbox) {
            checkbox.addEventListener('change', function() {
                label.innerText = checkbox.checked ? '🟢 Открыт набор' : '🔴 Набор закрыт';
            });
        }

        async function saveSettings(e) {
            e.preventDefault();
            var formData = new FormData(document.getElementById('settingsForm'));
            var data = Object.fromEntries(formData.entries());
            data.recruitment_open = checkbox.checked ? 1 : 0;

            var res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (res.ok) {
                var notify = document.getElementById('notify');
                notify.style.display = 'block';
                setTimeout(function() { notify.style.display = 'none'; }, 3000);
            }
        }
    </script>
</body>
</html>
"""

async def handle_dashboard(request):
    conn = database.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM guild_settings LIMIT 1")
    guild = cursor.fetchone()

    clan_name = guild["clan_name"] if guild else "116 clnx"
    review_channel_id = str(guild["review_channel_id"] or "") if guild else ""
    voice_channel_id = str(dict(guild).get("voice_channel_id") or "1414100339820331039") if guild else "1414100339820331039"
    recruiter_role_id = str(guild["recruiter_role_id"] or "1372603820441468948") if guild else "1372603820441468948"
    member_role_id = str(guild["member_role_id"] or "") if guild else ""
    banner_url = guild["banner_url"] if guild else ""
    pubg_banner_url = guild["pubg_banner_url"] if guild else ""
    is_open = guild["recruitment_open"] if guild else 1

    # Заявки
    cursor.execute("SELECT * FROM applications ORDER BY id DESC")
    apps = cursor.fetchall()

    apps_rows = ""
    status_badges = {
        "pending": '<span class="badge badge-pending">🟡 На рассмотрении</span>',
        "accepted": '<span class="badge badge-accepted">🟢 Принят</span>',
        "rejected": '<span class="badge badge-rejected">🔴 Отклонён</span>',
        "interview": '<span class="badge badge-interview">📞 На обзвоне</span>',
    }

    for app in apps:
        badge = status_badges.get(app["status"], app["status"])
        rollbacks = app["rollbacks"]
        if len(rollbacks) > 50:
            rollbacks = rollbacks[:47] + "..."
        apps_rows += f"""
        <tr>
            <td>#{app['id']}</td>
            <td><b>{app['user_tag']}</b></td>
            <td><code>{app['nickname_static']}</code></td>
            <td>{app['irl_name_age']}</td>
            <td><a href="{app['rollbacks']}" target="_blank" style="color: var(--blue);" title="{app['rollbacks']}">{rollbacks}</a></td>
            <td>{badge}</td>
        </tr>
        """

    if not apps_rows:
        apps_rows = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Заявок пока нет</td></tr>'

    # PUBG мероприятия
    cursor.execute("SELECT * FROM events ORDER BY id DESC")
    events = cursor.fetchall()
    pubg_rows = ""

    for ev in events:
        cursor.execute("SELECT * FROM event_participants WHERE event_id = ?", (ev["id"],))
        parts = cursor.fetchall()
        parts_list = ", ".join([f"{p['user_name']} ({p['static_id']} | {dict(p).get('team_name', '')})" for p in parts]) or "Нет участников"
        if len(parts_list) > 70:
            parts_list = parts_list[:67] + "..."

        status = '<span class="badge badge-rejected">🔒 Закрыто</span>' if ev["is_closed"] else '<span class="badge badge-accepted">🟢 Идёт регистрация</span>'
        pubg_rows += f"""
        <tr>
            <td><b>{ev['game_server']}</b></td>
            <td>{ev['event_time']}</td>
            <td>{ev['reg_deadline']}</td>
            <td><b>{len(parts)} чел.</b><br><small style="color: var(--text-muted);">{parts_list}</small></td>
            <td>{status}</td>
        </tr>
        """

    if not pubg_rows:
        pubg_rows = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Мероприятий пока не создано</td></tr>'

    conn.close()

    html = HTML_TEMPLATE
    replacements = {
        "{{clan_name}}": clan_name,
        "{{review_channel_id}}": review_channel_id,
        "{{voice_channel_id}}": voice_channel_id,
        "{{recruiter_role_id}}": recruiter_role_id,
        "{{member_role_id}}": member_role_id,
        "{{banner_url}}": banner_url,
        "{{pubg_banner_url}}": pubg_banner_url,
        "{{recruitment_checked}}": "checked" if is_open else "",
        "{{recruitment_text}}": "🟢 Открыт набор" if is_open else "🔴 Набор закрыт",
        "{{apps_count}}": str(len(apps)),
        "{{apps_rows}}": apps_rows,
        "{{pubg_rows}}": pubg_rows
    }

    for key, val in replacements.items():
        html = html.replace(key, val)

    return web.Response(text=html, content_type="text/html")


async def handle_save_settings(request):
    data = await request.json()
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id FROM guild_settings LIMIT 1")
    row = cursor.fetchone()
    guild_id = row["guild_id"] if row else 1
    conn.close()

    database.update_guild_settings(
        guild_id,
        clan_name=data.get("clan_name", "116 clnx"),
        review_channel_id=int(data["review_channel_id"]) if data.get("review_channel_id") else None,
        voice_channel_id=int(data["voice_channel_id"]) if data.get("voice_channel_id") else 1414100339820331039,
        recruiter_role_id=int(data["recruiter_role_id"]) if data.get("recruiter_role_id") else None,
        member_role_id=int(data["member_role_id"]) if data.get("member_role_id") else None,
        banner_url=data.get("banner_url", ""),
        pubg_banner_url=data.get("pubg_banner_url", ""),
        recruitment_open=int(data.get("recruitment_open", 1))
    )

    return web.json_response({"status": "ok"})


def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_dashboard)
    app.router.add_post("/api/settings", handle_save_settings)
    return app
