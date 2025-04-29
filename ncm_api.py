import log
import json
import pyncm
from pyncm import apis
from nicegui import ui

logger = log.logger

def get_ncm_search(keyword, limit=1):
    try:
        # 获取歌曲信息
        res = apis.cloudsearch.GetSearchResult(keyword=keyword, limit=limit) # 获取歌曲信息
        if res["code"] == 200:
            logger.info(f'get_ncm_search: {keyword} - 歌曲ID: {res["result"]["songs"][0]["id"]}')
            return res
        else:
            logger.error(f"get_ncm_search: 获取歌曲信息失败: {res['msg']}")
            return None
    except Exception as e:
        logger.error(f"get_ncm_search: 网易云发生未知错误: {e}")
        return None

def get_song_info(id):
    # try:
    info = apis.track.GetTrackDetail([id])
    if info["code"] == 200:
        if len(info['songs']) < 1:
            logger.error(f"get_song_info: 歌曲信息为空")
            return None

        logger.info(f"get_song_info: {info['songs'][0]['name']} {info['songs'][0]['ar'][0]['name']}")
        return info
    else:
        logger.error(f"get_song_info: 获取歌曲信息失败: {info['msg']}")
        return None
    # except Exception as e:
    #     logger.error(f"get_song_info: 网易云发生未知错误: {e}")
    #     return None

def get_url(id):
    info = apis.track.GetTrackAudio([id])
    return info

def auth_anonymous():
    """
    匿名登录ncm
    """

    apis.login.LoginViaAnonymousAccount()

def get_qrcode_status(unikey):
    """
    获取登录二维码状态
    """
    return apis.login.LoginQrcodeCheck(unikey=unikey)

def get_unikey():
    """
    获取登录二维码
    """
    unikey = apis.login.LoginQrcodeUnikey()
    print(unikey)
    return unikey["unikey"]

def send_captcha(phone, ctcode):
    result = apis.login.SetSendRegisterVerifcationCodeViaCellphone(phone, ctcode)
    if not result.get("code", 0) == 200:
        logger.error(f"auth_cellphone: {result['msg']}")
        ui.notify(f"auth_cellphone: {result['msg']}", type="negative")
    else:
        logger.info("已发送验证码")
        ui.notify("已发送验证码", type="positive")

def auth_cellphone(phone, captcha, ctcode):
    """
    手机验证码登录ncm
    """
    while True:
        verified = apis.login.GetRegisterVerifcationStatusViaCellphone(phone, captcha, ctcode)
        if verified.get("code", 0) == 200:
            logger.info("验证成功")
            break
    try:
        result = apis.login.LoginViaCellphone(phone, captcha=captcha, ctcode=ctcode)
        logger.debug(result)
    except Exception as e:
        logger.error(f"auth_cellphone: {e}")
        return False

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    session = pyncm.DumpSessionAsString(pyncm.GetCurrentSession())
    if session != "":
        config["ncm_session"] = session
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    else:
        return False

def auth_cookie(cookie):
    """
    cookie登录ncm
    """
    res = apis.login.LoginViaCookie(cookie)
    if res["code"] == 200 and apis.login.GetCurrentSession().nickname != "":
        return True
    else:
        return False

if __name__ == "__main__":
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    pyncm.SetCurrentSession(pyncm.LoadSessionFromString(config["ncm_session"]))
    session = apis.login.GetCurrentSession()
    print(session.nickname)