
import json, os, re, asyncio, shutil, pyncm, requests, signal, sys, datetime

import ncm_api
import bili_api
import update
import blivedm.blivedm.models.web as web_models
import blivedm.blivedm.models.open_live as open_models

from typing import *
from log import logger
from pyncm import apis
from nicegui import ui, app

from blivedm import blivedm

version = "1.3.0"
b_connect_status = False # 初始化弹幕服务器连接状态
app.add_static_files('/static', 'static')

example_config = {
                    "port": 8080,
                    "ACCESS_KEY_ID": "",
                    "ACCESS_KEY_SECRET": "",
                    "APP_ID": 0,
                    "auth_code": "",
                    "ncm_cookie": "",
                    "ncm_session": ""
                }

if not os.path.exists("config.json"):
    if not os.path.exists("config.example.json"):
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(example_config, f, ensure_ascii=False, indent=4
            )
    else:
        shutil.copy("config.example.json", "config.json")

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

diff = example_config.keys() - config.keys()

for key in diff:
    config[key] = example_config[key]
diff = config.keys() - example_config.keys()
for key in diff:
    config.pop(key, None)

with open("config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=4)

if not os.path.exists("danmaku.json"):
    with open("danmaku.json", "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=4)

ACCESS_KEY_ID = config.get("ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = config.get("ACCESS_KEY_SECRET", "")
APP_ID = int(config.get("APP_ID", 0))
ROOM_ID = 0

# 主播身份码
ROOM_OWNER_AUTH_CODE = config.get("auth_code") or None # 空字符串为False

danmaku_cd = {}

signal_list = (signal.SIGTERM, signal.SIGBREAK)

async def signal_handler(signum, frame):
    await client.stop_and_close()

if sys.platform == 'win32':
    for i in signal_list:
        signal.signal(i, signal_handler)

async def start_handler():
    await run_single_client()

async def run_single_client():
    global client
    client = blivedm.OpenLiveClient(
        access_key_id=ACCESS_KEY_ID,
        access_key_secret=ACCESS_KEY_SECRET,
        app_id=APP_ID,
        room_owner_auth_code=ROOM_OWNER_AUTH_CODE,
    )
    handler = BiliHandler()
    client.set_handler(handler)

    client.start()

    try:
        await client.join()
    finally:
        await client.stop_and_close()

# 获取弹幕信息
class BiliHandler(blivedm.BaseHandler):
    heart_count = 0
    # 心跳数据
    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        global ROOM_ID
        self.heart_count += 1
        logger.debug(f'[{client.room_id}] {message}')
        if self.heart_count < 2:
            b_connect_switch.set_value(True)
            b_connect_switch.set_text(f"已连接至: {client.room_id}")
            logger.info(f"已连接至{client.room_id}")
            ROOM_ID = client.room_id

            try:
                session = pyncm.GetCurrentSession().nickname
            except Exception as e:
                logger.error(f"_on_heartbeat_check_ncm_session: {e}")
                session = ""

            if session == "":
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                session = config["ncm_session"]
                if session != "":
                    pyncm.SetCurrentSession(pyncm.LoadSessionFromString(session))
                else:
                    if config["ncm_cookie"] != "":
                        ncm_api.auth_cookie(config["ncm_cookie"])

    def _on_open_live_danmaku(self, client: blivedm.OpenLiveClient, message: open_models.DanmakuMessage):
        user = message.uname
        msg = message.msg
        guard_level = message.guard_level
        is_admin = True if message.is_admin == 1 else False
        fans_medal_level = message.fans_medal_level
        status = False

        logger.info(f'[{client.room_id}] {user}：{msg}')

        if message.open_id == client._room_owner_open_id: # 如果用户Open ID = 主播Open ID，则为房管
            is_admin = True

        if msg.startswith("点歌"):
            if gift_checkbox.value: # 如果开启了礼物点歌
                with open("danmaku.json", "r", encoding="utf-8") as f:
                    danmaku_data = json.load(f)
                # 记录当前时间
                current_time = int(datetime.datetime.timestamp(datetime.datetime.now()))
                # 初始化用户记录
                if user not in danmaku_data:
                    danmaku_data[user] = {}
                # 更新弹幕时间
                danmaku_data[user]['danmaku'] = current_time
                # 检查该用户是否有送礼记录
                if 'gift' in danmaku_data.get(user, {}):
                    gift_time = danmaku_data[user]['gift']
                    if current_time >= gift_time: # 如果当前时间 ≥ 送礼时间
                        time_diff = int(current_time - gift_time) # 当前时间 - 送礼时间
                    else:
                        time_diff = int(gift_time - danmaku_data[user]['danmaku']) # 送礼时间 - 弹幕时间
                    # 判断是否在设定时间内
                    if time_diff >= int(delay_gift_time.value):
                        result = f"[弹幕在送礼前后{delay_gift_time.value / 60}分钟外] 用户: {user}, 时间差: {time_diff}秒"
                        logger.info(result)
                        with notify_card:
                            ui.notify(result)
                        try:
                            danmaku_data[user].pop('gift')
                            danmaku_data[user].pop('danmaku')
                        except Exception as e:
                            logger.warning(f"礼物记录出现错误: {e}")
                    else:
                        result = f"[弹幕在送礼前后{delay_gift_time.value / 60}分钟内] 用户: {user}, 时间差: {time_diff}秒"
                        logger.info(result)
                        status = True
                        try:
                            danmaku_data[user].pop('gift')
                            danmaku_data[user].pop('danmaku')
                        except Exception as e:
                            logger.warning(f"礼物记录出现错误: {e}")

            if danmaku_checkbox.value:
                current_time = int(datetime.datetime.timestamp(datetime.datetime.now()))
                # 初始化用户记录
                if user not in danmaku_cd:
                    danmaku_cd[user] = {}
                    danmaku_cd[user]["danmaku"] = 0
                if int(current_time - danmaku_cd[user]["danmaku"]) >= danmaku_time.value or danmaku_cd[user]["danmaku"] == 0:
                    status = True
                    danmaku_cd[user]['danmaku'] = current_time
                else:
                    if guard_level == 0 and not is_admin and not status:
                        with notify_card:
                            ui.notify(f"{user} - 点歌冷却中！cd: {int(danmaku_time.value + danmaku_cd[user]["danmaku"] - current_time)}秒")

            if fans_medal_checkbox and fans_medal_level >= fans_medal.value:
                status = True

            if len(msg.split("点歌")) > 1:
                song = msg.split("点歌")[1]
                if len(song) > 0 and song[0] == " " and song != None:
                    song = song[1:]

                if song == None:
                    pass
                else:
                    if guard_level > 0 or is_admin or status: # 如果是大航海或管理员或status为True
                        if danmaku_data.get(user, {}).get("special", False): # 如果用户有自定义礼物记录
                            with notify_card:
                                ui.notify(f"感谢{user}的支持，愿世界永保和平！")

                        get_song_info(song, True)

                        try:
                            danmaku_data[user].pop('gift')
                            danmaku_data[user].pop('danmaku')
                        except Exception as e:
                            logger.warning(f"礼物记录出现错误: {e}")

            with open("danmaku.json", "w+", encoding="utf-8") as f:
                    json.dump(danmaku_data, f, ensure_ascii=False, indent=4)

    def _on_open_live_gift(self, client: blivedm.OpenLiveClient, message: open_models.GiftMessage):
        user = message.uname
        gift = message.gift_name
        price = message.r_price * message.gift_num
        is_paid = message.paid
        current_time = int(datetime.datetime.timestamp(datetime.datetime.now()))
        custom_gifts = ["昏睡红茶", "Nya冰美式"]
        base_price = 0

        logger.info(f'[{message.room_id}] {user} 赠送{gift}x{message.gift_num}')

        ### debug ###
        if gift == "辣条" and message.room_id == 31842:
            is_paid = True
            print(f"礼物：{gift}，价格：{price}，用户：{user}，房间号：{message.room_id}，时间：{current_time}")
        ### debug ###

        if gift_checkbox.value: # 如果开启了礼物点歌
            gift_list = bili_api.get_room_gift("android", message.room_id)["data"]["gift_config"]["base_config"]["list"]

            if gift_list:
                for i in gift_list:
                    if i["name"] == gift_select.value:
                        base_price = i["price"] # 获取设定礼物价格
            else:
                base_price = 5000 # 如果无法获取设定礼物价格则默认为50电池（5000金瓜子）

            if gift == gift_select.value or gift in custom_gifts or price >= base_price: # 赠送了设定礼物或自定义礼物或实际礼物价值大于设定礼物
                if is_paid: # 如果是电池礼物
                    with open("danmaku.json", "r", encoding="utf-8") as f:
                        danmaku_data = json.load(f)

                    # 初始化用户记录
                    if user not in danmaku_data:
                        danmaku_data[user] = {}

                    # 用户赠送自定义礼物
                    if gift in custom_gifts:
                        danmaku_data[user]["special"] = True

                    # 更新送礼时间
                    danmaku_data[user]['gift'] = current_time
                    logger.info(f'[{message.room_id}] {user} 赠送{gift}x{message.gift_num}')

                    with open("danmaku.json", "w+", encoding="utf-8") as f:
                        json.dump(danmaku_data, f, ensure_ascii=False, indent=4)

    def _on_open_live_buy_guard(self, client: blivedm.OpenLiveClient, message: open_models.GuardBuyMessage):
        logger.info(f'[{message.room_id}] {message.user_info.uname} 购买 大航海等级={message.guard_level}')


# 检查版本更新按钮
def check_update(init = False):
    def version_dialog():
        with ui.dialog() as dialog, ui.card(align_items="center"):
            ui.label(f"当前版本：v{version} | 最新版本：v{status}")

            with ui.row():
                ui.button("国内源", on_click=lambda: update.update("CN-HK"))
                ui.button("海外源", on_click=lambda: update.update("Overseas")).disable()
                ui.button("GitHub", on_click=lambda: update.update("GitHub"))
                ui.button("取消", on_click=lambda: dialog.close())

        dialog.open()

    def version_check():
        url = ["http://version.nya-wsl.cn/bili_ncm/version.txt", "https://nya-wsl.com/bili_ncm/version.txt"]
        try:
            latest_version = requests.get(url[0]) # 优先从Nya-WSL中国服务器获取版本信息
            if latest_version.status_code == 200:
                latest_version = latest_version.text.replace("\n", "") # 服务器返回内容
            else:
                raise ValueError("From Nya-WSL CN to get version info was error") # 抛出错误
        except:
            try:
                latest_version = requests.get(url[1]) # 从Nya-WSL海外服务器获取版本信息
                if latest_version.status_code == 200: # 服务器请求返回值
                    latest_version = latest_version.text.replace("\n", "") # 服务器返回内容
                else:
                    latest_version = "Error"
            except:
                latest_version = "Error" # 如果请求均失败版本信息设为"Error"

        return latest_version

    status = version_check()
    if status != version:
        if status != "Error":
            if init:
                ui.notify(f"检查到可用更新：v{status}", progress=True, timeout=10000, color="orange-10")
            else:
                version_dialog()
        else:
            ui.notify("检查更新失败", type="negative")
    else:
        ui.notify("已是最新版本", type="positive")

async def check_b_connect_status():
    global b_connect_status
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    # 如果连接弹幕服务器开关为关且身份码不为空
    if b_connect_switch.value == False:
        if ROOM_OWNER_AUTH_CODE == None:
            if not b_connect_status:
                b_connect_switch.set_value(False)
                return
            else:
                b_connect_status = False
                await client.stop_and_close() # 断开弹幕服务器ws连接并关闭blivedm客户端
                ui.notify("已断开连接，这通常是因为手动关闭了连接或身份码不正确")
                b_connect_switch.set_value(False)
                b_connect_switch.set_text("连接至弹幕服务器")
        else:
            b_connect_status = False
            try:
                await client.stop_and_close() # 断开弹幕服务器ws连接并关闭blivedm客户端
                logger.info("弹幕服务器ws连接已断开")
                ui.notify("已断开连接，这通常是因为手动关闭了连接或身份码不正确")
            except Exception as e:
                logger.warning(e)
            b_connect_switch.set_value(False)
            b_connect_switch.set_text("连接至弹幕服务器")

    if b_connect_switch.value == "null":
        if ROOM_OWNER_AUTH_CODE == None:
            b_connect_switch.set_value(False)
            return

        if not b_connect_status:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            if ROOM_OWNER_AUTH_CODE == None:
                ui.notify("未填入身份码，无法连接弹幕服务器", type="negative")
                b_connect_switch.set_value(False)
                return
            asyncio.create_task(start_handler()) # 创建连接弹幕服务器协程
            b_connect_switch.set_value("null")
            b_connect_switch.set_text("尝试连接弹幕服务器")
            b_connect_status = True # 设置弹幕服务器连接状态
        else:
            b_connect_switch.set_value(True)

    # 如果连接弹幕服务器开关为开
    if b_connect_switch.value == True:
        if ROOM_OWNER_AUTH_CODE == None: # 如果身份码为空
            ui.notify("请输入身份码", type="negative")
            b_connect_switch.set_value(False) # 重置开关为关
            return

        if not b_connect_status:
            b_connect_switch.set_value("null")

def save_config():
    with open("config.json", "w+", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

async def change_list(on = False):
    with open("aplayer.json", "r", encoding="utf-8") as f:
        audio = json.load(f)
    with open("playlist.json", "r", encoding="utf-8") as f:
        playlist = json.load(f)
    if len(audio) > 0:
        audio.pop(0)
        with open("aplayer.json", "w", encoding="utf-8") as f:
            json.dump(audio, f, ensure_ascii=False, indent=4)
    if len(playlist) > 0:
        playlist.pop(0)
        with open("playlist.json", "w", encoding="utf-8") as f:
            json.dump(playlist, f, ensure_ascii=False, indent=4)

    if not on:
        send('list.remove(0)')
        send('list.hide()')
        await asyncio.sleep(0.5)
        send('list.show()')

    try:
        list_num.set_options(get_list_num()) # 更新列表序号
    except NameError:
        logger.warning("更新列表序号失败，可能在主窗口创建前访问了播放器，如果是请忽略")

def clear_list():
    def clear_list_fun():
        with open("aplayer.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
        with open("playlist.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
        send("list.clear()")
        list_num.set_options(get_list_num()) # 更新列表序号
        double_check.close()

    with ui.dialog(value=True) as double_check, ui.card(align_items="center"):
        ui.label("确定清空列表？")
        with ui.row():
            ui.button("清空", on_click=lambda: clear_list_fun())
            ui.button("取消", on_click=lambda: double_check.close())

def del_list(num):
    if num != None or num != "":
        with open("aplayer.json", "r", encoding="utf-8") as f:
            audio = json.load(f)
        with open("aplayer.json", "w", encoding="utf-8") as f:
            audio.pop(num - 1)
            json.dump(audio, f, ensure_ascii=False, indent=4)

        with open("playlist.json", "r", encoding="utf-8") as f:
            playlist = json.load(f)
        with open("playlist.json", "w", encoding="utf-8") as f:
            playlist.pop(num - 1)
            json.dump(playlist, f, ensure_ascii=False, indent=4)

        send(f'list.remove({num - 1})')
        list_num.set_options(get_list_num()) # 更新列表序号
        list_num.set_value(None) # 重置列表序号选择框的值

def get_list_num():
    with open("aplayer.json", "r", encoding="utf-8") as f:
        return list(range(1, len(json.load(f)) + 1))

def get_song_info(keyword, add = False, limit = 1):
    id = None

    if keyword == None or keyword == "":
        logger.error("id不存在")
        return

    if not re.search(r"^\d+$", keyword):
        song = ncm_api.get_ncm_search(keyword, limit)
        with open("playlist.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        id = song["result"]["songs"][0]["id"]
        data.append(id)
    else:
        with open("playlist.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        info = ncm_api.get_song_info(keyword)
        if info == None:
            logger.error("id不存在")
            return
        id = info["songs"][0]["id"]
        data.append(id)

    with open("playlist.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    if add:
        ncm_to_player(id, True)
    else:
        ncm_to_player(id)

def get_audio_url(id):
    """
    获取歌曲直链
    """

    return ncm_api.get_url(id)["data"][0]["url"]

def ncm_to_player(id = None, add = False):
    """
    将playlist.json的网易云id转换为aplayer.json的直链
    """
    with open("playlist.json", "r", encoding="utf-8") as f:
        playlist = json.load(f)
    if id == None:
        audio = []

        try:
            nickname = pyncm.GetCurrentSession().nickname
        except Exception as e:
            logger.error(f"ncm_to_player: {e}")
            nickname = ""

        if nickname == "":
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            try:
                ncm_api.auth_cookie(config["ncm_cookie"])
            except Exception as e:
                logger.error(f"ncm_to_player: {e}")

        for id in playlist:
            info = ncm_api.get_song_info(id)
            if info != None:
                audio.append(
                    {
                        "name": info["songs"][0]["name"],
                        "artist": info["songs"][0]["ar"][0]["name"],
                        "url": get_audio_url(info["songs"][0]["id"]),
                        "cover": info["songs"][0]["al"]["picUrl"],
                        "lrc": apis.track.GetTrackLyrics(id)["lrc"]["lyric"]
                    }
                )
        with open("aplayer.json", "w", encoding="utf-8") as f:
            json.dump(audio, f, ensure_ascii=False, indent=4)
        return audio
    else:
        with open("aplayer.json", "r", encoding="utf-8") as f:
            audio = json.load(f)
        info = ncm_api.get_song_info(id)
        if info != None:
            audio.append(
                {
                    "name": info["songs"][0]["name"],
                    "artist": info["songs"][0]["ar"][0]["name"],
                    "url": get_audio_url(info["songs"][0]["id"]),
                    "cover": info["songs"][0]["al"]["picUrl"],
                    "lrc": apis.track.GetTrackLyrics(id)["lrc"]["lyric"]
                }
            )
            if add:
                song = [
                    {
                        "name": info["songs"][0]["name"],
                        "artist": info["songs"][0]["ar"][0]["name"],
                        "url": get_audio_url(info["songs"][0]["id"]),
                        "cover": info["songs"][0]["al"]["picUrl"],
                        "lrc": apis.track.GetTrackLyrics(id)["lrc"]["lyric"]
                    }
                    ]
                send(f'list.add({song})')
                send("list.show()")
        with open("aplayer.json", "w", encoding="utf-8") as f:
            json.dump(audio, f, ensure_ascii=False, indent=4)
        list_num.set_options(get_list_num()) # 更新列表序号

def check_auth():
    stasus = False
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    session_str = config["ncm_session"]
    if session_str != "":
        pyncm.SetCurrentSession(pyncm.LoadSessionFromString(session_str))
        stasus = True

    try:
        session = pyncm.GetCurrentSession().nickname
    except Exception as e:
        logger.error(f"check_auth: {e}")
        session = ""

    if session != "":
        stasus = True

    if stasus:
        ui.notify("网易云已登录：" + session, type="positive")
    else:
        ui.notify("网易云登录态失效或未登录", type="negative")

if not os.path.exists("aplayer.json"):
    with open("aplayer.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)

if not os.path.exists("playlist.json"):
    with open("playlist.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)

# APlayer 的 CDN 资源（JS 和 CSS）
aplayer_js = "/static/aplayer/APlayer.min.js"
aplayer_css = "/static/aplayer/APlayer.min.css"

@ui.page('/player')
def _():
    global notify_card
    # 在页面头部加载资源
    ui.add_head_html(f'''
        <link rel="stylesheet" href="{aplayer_css}">
        <script src="{aplayer_js}"></script>
    ''')

    volume = float(app.storage.general["volume"]) / 100

    ui.add_body_html(f'''
        <div id="aplayer"></div>
        <script>
            const ap = new APlayer({{
                container: document.getElementById('aplayer'), // 指定播放器容器
                lrcType: 1, // 指定歌词类型
                volume: {volume}, // 指定音量
                audio: {ncm_to_player()}, // 指定音频列表
                autoplay: true, // 是否自动播放,
                listMaxHeight: 1024, // 列表最大高度
            }});
            ap.volume({volume}, true); // 设置音量
            ap.on('ended', function () {{
                ap.list.remove(ap.list.index - 1); // index为下一首歌，需-1
                ap.list.hide() // aplayer在移除时不会自动更新列表，需手动刷新一次
                ap.list.show()
                emitEvent('ap_ended'); // 创建自定义监听：播放结束
                ap.play();
            }});
        </script>
    ''')

    ui.on('ap_ended', lambda: change_list(True)) # 监听自定义的播放结束事件

    with ui.card().classes("bg-transparent w-full").style("box-shadow: None;") as notify_card:
        ui.label().set_visibility(False)

def send(msg: str):
    for client in app.clients("/player"):
        with client:
            ui.run_javascript(f'ap.{msg}')

def check_cellphone(phone, captcha, ctcode):
    result = ncm_api.auth_cellphone(phone, captcha, ctcode)
    if result:
        ui.notify("登录成功", type="positive")
    else:
        ui.notify("登录失败", type="negative")

port = config["port"]

@ui.page("/")
def _():
    global b_connect_switch, list_num, danmaku_checkbox, gift_checkbox, danmaku_time, delay_gift_time, gift_select, fans_medal, fans_medal_checkbox
    # with open("config.json", "r", encoding="utf-8") as f:
    #     config = json.load(f)

    def notify():
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        ui.notify("登录成功", type="positive") if ncm_api.auth_cookie(config["ncm_cookie"]) else ui.notify("cookie登录失败", type="negative")

    def update_auth_code(value):
        global ROOM_OWNER_AUTH_CODE
        ROOM_OWNER_AUTH_CODE = value
        save_config()
    
    def get_gift():
        gifts = bili_api.get_room_gift("android", ROOM_ID)
        if not gifts:
            return {"not_connect": "未连接至弹幕服务器"}
        else:
            gift_list = []
            gifts = gifts["data"]["gift_config"]["base_config"]["list"]
            for gift in gifts:
                gift_list.append(gift["name"])
            if ROOM_ID == 31842:
                gift_list.append("辣条")
            return gift_list

    with ui.dialog() as auth_dialog, ui.card(align_items="center"):
        ui.label("网易云音乐")
        with ui.row():
            ctcode = ui.input("国家代码(默认86)", value="86")
            cellphone = ui.input("手机号")
        captcha = ui.input("验证码")
        with ui.row():
            ui.button("发送验证码", on_click=lambda: ncm_api.send_captcha(cellphone.value, ctcode.value)).on_click(lambda: captcha.set_value("")).on_click(lambda: login_button.enable())
            login_button = ui.button("登录", on_click=lambda: check_cellphone(cellphone.value, captcha.value, ctcode.value))
            login_button.disable()
            ui.button("使用cookie登录", on_click=lambda: notify())

    with ui.dialog() as base_config_dialog, ui.card(align_items="center"):
        with ui.row():
            danmaku_checkbox = ui.checkbox("弹幕点歌", value=True).bind_value(app.storage.general, "danmaku_status")
            gift_checkbox = ui.checkbox("礼物点歌", value=True).bind_value(app.storage.general, "gift_status")
            fans_medal_checkbox = ui.checkbox("粉丝勋章", value=False).bind_value(app.storage.general, "fans_medal_status")
        danmaku_time = ui.number("弹幕点歌冷却(秒)", value=0, min=0).bind_value(app.storage.general, "danmaku_time").style("width: 100px;")
        delay_gift_time = ui.number("礼物点歌延时(秒)", value=0, min=0).bind_value(app.storage.general, "gift_time").style("width: 100px;")
        with ui.number("粉丝勋章等级", value=1, min=1).bind_value(app.storage.general, "fans_medal_level").style("width: 100px;") as fans_medal:
            ui.tooltip("粉丝勋章大于该等级将无视规则直接点歌")
        ui.button("确定", on_click=lambda: base_config_dialog.close())

    with ui.card(align_items="center").classes("absolute-center w-2/3"):
        ui.input("身份码", password=True, password_toggle_button=True, on_change=lambda e: update_auth_code(e.value)).bind_value(config, "auth_code")
        b_connect_switch = ui.switch("连接至弹幕服务器", on_change=lambda: check_b_connect_status()).props('checked-icon="check" color="green" unchecked-icon="clear"')

        with ui.row():
            gift_select = ui.select(options=get_gift(), label="选择礼物", with_input=True, clearable=True).style("width: 150px;").bind_value(app.storage.general, "gift_name").on("open")
            ui.button("刷新", on_click=lambda: gift_select.set_options(get_gift()))

        with ui.row():
            manual_keyword = ui.input("歌曲id").style("width: 150px;")
            manual_keyword.tooltip("输入歌曲id或网易云链接")
            ui.button("搜索", on_click=lambda: get_song_info(match.group() if (match := re.search(r"(?<=id=)\d+", manual_keyword.value)) else manual_keyword.value, add=True)).on_click(lambda: manual_keyword.set_value(""))
        with ui.row():
            list_num = ui.select(options=get_list_num(), label="歌单序号").style("width: 150px;")
            ui.button("删除", on_click=lambda: del_list(list_num.value))
        with ui.row():
            ui.button("播放", on_click=lambda: send('play()'))
            ui.button("暂停", on_click=lambda: send('pause()'))
            ui.button("切歌", on_click=lambda: change_list())
            ui.button("清空", on_click=lambda: clear_list())
        with ui.row(align_items="center"):
            ui.button("上一首", on_click=lambda: send('skipBack()'))
            ui.button("下一首", on_click=lambda: send('skipForward()'))

        ui.label() # 占位符
        ui.slider(min=0, max=100, step=1, value=20, on_change=lambda e: send(f'volume({e.value / 100}, true)')).bind_value(app.storage.general, "volume").props('label-always')

        with ui.row():
            ui.button("点歌设置", on_click=lambda: base_config_dialog.open())
            ui.button("账号登录", on_click=lambda: auth_dialog.open())
            ui.button("检查更新", on_click=lambda: check_update())
        with ui.link(f"http://127.0.0.1:{port}/player", f"http://127.0.0.1:{port}/player", new_tab=True):
            ui.tooltip("OBS浏览器源URL")

    check_update(True)
    ui.timer(300, lambda: check_auth())

ui.run(port=port, title=f"bili_ncm | v{version}", native=True, reload=False, window_size=[660, 760])