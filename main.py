
import json, os, re, aiohttp, http.cookies, asyncio, shutil, pyncm, requests

import ncm_api
import update
import blivedm.blivedm.models.web as web_models

from typing import *
from log import logger
from pyncm import apis
from nicegui import ui, app

from blivedm import blivedm

version = "1.1.1"
b_connect_status = False # 初始化弹幕服务器连接状态
app.add_static_files('/static', 'static')

# 弹幕数据连接
async def start_handler():
    global client

    # 读入配置文件
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    # 直播间ID的取值看直播间URL
    ROOM_ID = config["room_id"]

    # 这里填一个已登录账号的cookie的SESSDATA字段的值。不填也可以连接，但是收到弹幕的用户名会打码，UID会变成0
    SESSDATA = config["bili_sessdata"]

    session: Optional[aiohttp.ClientSession] = None

    # 创建ws
    try:
        cookies = http.cookies.SimpleCookie()
        cookies['SESSDATA'] = SESSDATA
        cookies['SESSDATA']['domain'] = 'bilibili.com'

        session = aiohttp.ClientSession()
        session.cookie_jar.update_cookies(cookies)

        room_id = ROOM_ID
        client = blivedm.BLiveClient(room_id, session=session)
        handler = BiliHandler()
        client.set_handler(handler)
        client.start()

        try:
            await client.join()
        finally:
            await client.stop_and_close()

    finally:
        await session.close()

# 获取弹幕信息
class BiliHandler(blivedm.BaseHandler):
    heart_count = 0
    # 心跳数据
    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        self.heart_count += 1
        logger.debug(f'[{client.room_id}] {message}')
        if self.heart_count < 2:
            b_connect_switch.set_value(True)
            b_connect_switch.set_text("已连接弹幕服务器")
            logger.info(f"已连接至{room_id.value}")
            if pyncm.GetCurrentSession().nickname == "":
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                session = config["ncm_session"]
                if session != "":
                    pyncm.SetCurrentSession(pyncm.LoadSessionFromString(session))
                else:
                    if config["ncm_cookie"] != "":
                        ncm_api.auth_cookie(config["ncm_cookie"])

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        user = message.uname
        msg = message.msg

        logger.info(f'[{client.room_id}] {user}：{msg}')
        if msg.startswith("点歌"):
            if len(msg.split("点歌")) > 1:
                song = msg.split("点歌")[1]
                if len(song) > 0 and song[0] == " " and song != None:
                    song = song[1:]

                if song == None:
                    pass
                else:
                    get_song_info(song, True)

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

    # 如果连接弹幕服务器开关为关且房间号不为空
    if b_connect_switch.value == False:
        if room_id.value == "":
            if not b_connect_status:
                b_connect_switch.set_value(False)
                return
            else:
                b_connect_status = False
                await client.stop_and_close() # 断开弹幕服务器ws连接并关闭blivedm客户端
                ui.notify("已断开连接，这通常是因为手动关闭了连接或房间号不正确")
                b_connect_switch.set_value(False)
                b_connect_switch.set_text("连接至弹幕服务器")
        else:
            b_connect_status = False
            await client.stop_and_close() # 断开弹幕服务器ws连接并关闭blivedm客户端
            ui.notify("已断开连接，这通常是因为手动关闭了连接或房间号不正确")
            b_connect_switch.set_value(False)
            b_connect_switch.set_text("连接至弹幕服务器")

    if b_connect_switch.value == "null":
        if room_id.value == "":
            b_connect_switch.set_value(False)
            return

        if not b_connect_status:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            if config["bili_sessdata"] == "":
                ui.notify("未登录B站账号，可能无法显示用户名", type="warning")
            asyncio.create_task(start_handler()) # 创建连接弹幕服务器协程
            b_connect_switch.set_value("null")
            b_connect_switch.set_text("尝试连接弹幕服务器")
            b_connect_status = True # 设置弹幕服务器连接状态
        else:
            b_connect_switch.set_value(True)

    # 如果连接弹幕服务器开关为开
    if b_connect_switch.value == True:
        if room_id.value == "": # 如果房间号为空
            ui.notify("请输入房间号", type="negative")
            b_connect_switch.set_value(False) # 重置开关为关
            return

        if not b_connect_status:
            b_connect_switch.set_value("null")

def save_config():
    with open("config.json", "w+", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def change_list():
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

    send('list.remove(0)')
    list_num.set_options(get_list_num()) # 更新列表序号

def clear_list():
    with open("aplayer.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)
    with open("playlist.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)
    send("list.clear()")
    list_num.set_options(get_list_num()) # 更新列表序号

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
        if pyncm.GetCurrentSession().nickname == "":
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            ncm_api.auth_cookie(config["ncm_cookie"])

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

    session = pyncm.GetCurrentSession()
    if session.nickname != "":
        stasus = True

    if stasus:
        ui.notify("网易云已登录：" + session.nickname, type="positive")
    else:
        ui.notify("网易云登录态失效或未登录", type="negative")

if not os.path.exists("aplayer.json"):
    with open("aplayer.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)

if not os.path.exists("playlist.json"):
    with open("playlist.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=4)

example_config = {
                    "port": 8080,
                    "room_id": "",
                    "bili_sessdata": "",
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

    # APlayer 的 CDN 资源（JS 和 CSS）
    aplayer_js = "/static/aplayer/APlayer.min.js"
    aplayer_css = "/static/aplayer/APlayer.min.css"

@ui.page('/player')
def _():
    # 在页面头部加载资源
    ui.add_head_html(f'''
        <link rel="stylesheet" href="{aplayer_css}">
        <script src="{aplayer_js}"></script>
    ''')

    with ui.card(align_items="center").classes("bg-transparent").style("box-shadow: None; left: 50%; transform: translate(-50%, 0%);"):
        ui.add_body_html(f'''
            <div id="aplayer"></div>
            <script>
                const ap = new APlayer({{
                    container: document.getElementById('aplayer'), // 指定播放器容器
                    lrcType: 1, // 指定歌词类型
                    audio: {ncm_to_player()}, // 指定音频列表
                    autoplay: true, // 是否自动播放,
                    listMaxHeight: 20, // 列表最大高度
                }});
            </script>
        ''')

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
    global room_id, b_connect_switch, list_num
    # with open("config.json", "r", encoding="utf-8") as f:
    #     config = json.load(f)

    def notify():
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        ui.notify("登录成功", type="positive") if ncm_api.auth_cookie(config["ncm_cookie"]) else ui.notify("cookie登录失败", type="negative")

    with ui.dialog() as auth_dialog, ui.card(align_items="center"):
        with ui.row():
            ctcode = ui.input("国家代码(默认86)", value="86")
            cellphone = ui.input("手机号")
        captcha = ui.input("验证码")
        with ui.row():
            ui.button("发送验证码", on_click=lambda: ncm_api.send_captcha(cellphone.value, ctcode.value)).on_click(lambda: captcha.set_value("")).on_click(lambda: login_button.enable())
            login_button = ui.button("登录", on_click=lambda: check_cellphone(cellphone.value, captcha.value, ctcode.value))
            login_button.disable()
            ui.button("使用cookie登录", on_click=lambda: notify())

    with ui.card(align_items="center").classes("absolute-center"):
        room_id = ui.input("房间号", on_change=lambda: save_config()).style("width: 150px").bind_value(config, "room_id")
        b_connect_switch = ui.switch("连接至弹幕服务器", on_change=lambda: check_b_connect_status()).props('checked-icon="check" color="green" unchecked-icon="clear"')
        with ui.row():
            manual_keyword = ui.input("歌曲id").style("width: 150px;")
            manual_keyword.tooltip("输入歌曲id或网易云链接")
            ui.button("搜索", on_click=lambda: get_song_info(match.group() if (match := re.search(r"(?<=id=)\d+", manual_keyword.value)) else manual_keyword.value)).on_click(lambda: manual_keyword.set_value(""))
        with ui.row():
            list_num = ui.select(options=get_list_num(), label="歌单序号").style("width: 150px;")
            ui.button("删除", on_click=lambda: del_list(list_num.value))
        with ui.row():
            ui.button("播放", on_click=lambda: send('play()'))
            ui.button("暂停", on_click=lambda: send('pause()'))
            ui.button("切歌", on_click=lambda: change_list())
            ui.button("清空", on_click=lambda: clear_list())
        with ui.row():
            ui.button("登录网易云", on_click=lambda: auth_dialog.open())
            ui.button("检查更新", on_click=lambda: check_update())
        with ui.row():
            ui.label(f"OBS浏览器源URL:")
            ui.link(f"http://127.0.0.1:{port}/player", f"http://127.0.0.1:{port}/player", new_tab=True)

    check_update(True)
    ui.timer(300, lambda: check_auth())

ui.run(port=port, title=f"bili_ncm | v{version}", native=True, reload=False)