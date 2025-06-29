import requests

def get_room_gift(platform, room_id):
    """
    :param: platform: e.g. 'android', 'pc'.
    :param: room_id: 房间号.
    """
    url = f"https://api.live.bilibili.com/xlive/web-room/v1/giftPanel/roomGiftList?platform={platform}&room_id={room_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
    }
    res = requests.get(url=url, headers=headers)
    res_json = res.json()
    return res_json if res.status_code == 200 and res_json["code"] == 0 else False

if __name__ == "__main__":
    data = get_room_gift('android', 1815222606)
    print(data["data"]["gift_config"]["base_config"]["list"])