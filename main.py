
import json, os, re, asyncio, shutil, pyncm, requests, signal, sys, datetime

import env # 该模块仅在打包时自动生成，打包后将会删除
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

version = "1.3.1-alpha"
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

if not os.path.exists("song.json"):
    with open("song.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)

# 需申请哔哩哔哩直播开放平台开发者账号并将id、key和app_id填入config.json中，如需开箱即用请在 https://github.com/Nya-WSL/bili_ncm/releases 下载
bili_keys = env.get_key()

if config.get("ACCESS_KEY_ID", "") != "":
    ACCESS_KEY_ID = config.get("ACCESS_KEY_ID", "")
else:
    ACCESS_KEY_ID = bili_keys.get("ACCESS_KEY_ID", "")

if config.get("ACCESS_KEY_SECRET", "") != "":
    ACCESS_KEY_SECRET = config.get("ACCESS_KEY_SECRET", "")
else:
    ACCESS_KEY_SECRET = bili_keys.get("ACCESS_KEY_SECRET", "")

if config.get("APP_ID", 0) != 0:
    APP_ID = int(config.get("APP_ID", 0))
else:
    APP_ID = int(bili_keys.get("APP_ID", 0))

ROOM_ID = 0

# 主播身份码
ROOM_OWNER_AUTH_CODE = config.get("auth_code") or None # 空字符串为False

danmaku_cd = {}

async def start_handler():
    await run_single_client()

@app.on_shutdown
async def shut_down():
    await client.stop_and_close()
    logger.info('ws connect shut down')

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

                    with notify_card:
                        ui.notify(result)

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

            if fans_medal_checkbox.value and fans_medal_level >= fans_medal.value:
                status = True

            if len(msg.split("点歌")) > 1:
                song = msg.split("点歌")[1]
                if len(song) > 0 and song[0] == " " and song != None:
                    song = song.strip().split(" ")

                    try:
                        artist = song[1]
                    except:
                        artist = ""

                    song = song[0]

                if song == None:
                    pass
                else:
                    if guard_level > 0 or is_admin or status: # 如果是大航海或管理员或status为True
                        append_song(song, artist)

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

            if gift == gift_select.value or price >= base_price: # 赠送了设定礼物或实际礼物价值大于设定礼物
                if is_paid: # 如果是电池礼物
                    with open("danmaku.json", "r", encoding="utf-8") as f:
                        danmaku_data = json.load(f)

                    # 初始化用户记录
                    if user not in danmaku_data:
                        danmaku_data[user] = {}


                    # 更新送礼时间
                    danmaku_data[user]['gift'] = current_time
                    logger.info(f'[{message.room_id}] {user} 赠送{gift}x{message.gift_num}')

                    with open("danmaku.json", "w+", encoding="utf-8") as f:
                        json.dump(danmaku_data, f, ensure_ascii=False, indent=4)

    def _on_open_live_buy_guard(self, client: blivedm.OpenLiveClient, message: open_models.GuardBuyMessage):
        logger.info(f'[{message.room_id}] {message.user_info.uname} 购买 大航海等级={message.guard_level}')

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

def change_list():
    with open("song.json", "r", encoding="utf-8") as f:
        songs = json.load(f)

    songs.pop(0)

    with open("song.json", "w+", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=4)

def clear_list():
    with open("song.json", "w+", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)

def append_song(song, artist = ""):
    with open("song.json", "r", encoding="utf-8") as f:
        songs = json.load(f)

    songs.append({"song": song, "artist": artist})

    with open("song.json", "w+", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=4)

port = config["port"]

@ui.page("/player")
def _():
    global notify_card

    def create_card():
        with open("song.json", "r", encoding="utf-8") as f:
            songs = json.load(f)
        for song in songs:
            with ui.row(align_items="center").classes("w-full"):
                ui.label(song["song"])
                ui.space()
                ui.label(song["artist"])

    def refresh_card():
        song_card.clear()
        with song_card:
            create_card()

    with ui.card().classes("bg-transparent").style("box-shadow: None; left: 50%; transform: translate(-50%, 0%);") as song_card:
        create_card()

    with ui.card().classes("bg-transparent w-full").style("box-shadow: None;") as notify_card:
        ui.label("").set_visibility(False)

    ui.timer(5, lambda: refresh_card())

@ui.page("/")
def _():
    global b_connect_switch, danmaku_checkbox, gift_checkbox, danmaku_time, delay_gift_time, gift_select, fans_medal, fans_medal_checkbox

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
            ui.button("切歌", on_click=lambda: change_list())
            ui.button("清空", on_click=lambda: clear_list())

        with ui.row():
            ui.button("点歌设置", on_click=lambda: base_config_dialog.open())

        with ui.link(f"http://127.0.0.1:{port}/player", f"http://127.0.0.1:{port}/player", new_tab=True):
            ui.tooltip("OBS浏览器源URL")

ui.run(port=port, title=f"bili_canción | v{version}", native=True, reload=False, window_size=[660, 760])