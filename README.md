# 基于blivedm和NiceGUI的BILIBILI网易云点歌姬

![version](https://img.shields.io/badge/Version-1.1.2-cyan) ![python](https://img.shields.io/badge/Python->=3.9,<3.14-blue) ![os](https://img.shields.io/badge/OS-Windows|Linux|MacOS-orange)

### Usage

- OBS添加浏览器源 `http:127.0.0.1:{port}/player`
- 浏览器源设置勾选 `通过OBS控制音频` `当不可见时关闭源` `当场景变为活动状态时，刷新浏览器`
- 如果希望更细致地控制播放器，可以使用OBS的交互按钮与播放器页面交互
- 根据系统的音频输出设置修改OBS浏览器源高级音频设置

### Feature

- [x] 支持lrc歌词（自动从网易云获取）
- [x] 支持切歌/清空歌单/循环模式/播放顺序/调整音量/歌曲列表
- [x] 登录网易云后支持vip歌曲
- [x] 支持手机验证码登录网易云 
- [x] 支持弹幕/手动使用网易云歌曲ID点歌
- [x] 支持删除歌单指定歌曲
- [ ] 支持登录B站账号后可根据用户状态点歌（例：是否房管、用户等级、是否舰长、牌子等级、SC点歌...）

### Screenshot

![图片](https://github.com/user-attachments/assets/469efe44-dd3b-4e48-9547-6b02bb015ec1)
![图片](https://github.com/user-attachments/assets/5eeb91ef-16c2-4eff-aafb-b26aee2c4749)
