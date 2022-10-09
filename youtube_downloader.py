from selenium import webdriver
import json
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By
from moviepy.editor import *
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException
import re
import keyboard
from ffpyplayer.player import MediaPlayer
import ffpyplayer.tools as tools
from datetime import timedelta
import os


class YoutubeDownloader:
    def __init__(self):
        self.path_to_extension = os.path.abspath("adblock")
        chrome_options = Options()
        chrome_options.add_argument('load-extension=' + self.path_to_extension)
        chrome_options.add_argument('--headless')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        capabilities = DesiredCapabilities.CHROME
        capabilities['goog:loggingPrefs'] = {"performance": "ALL"}
        self.browser = webdriver.Chrome('chromedriver.exe', desired_capabilities=capabilities,
                                        chrome_options=chrome_options)
        self.browser.create_options()
        self.wait = WebDriverWait(self.browser, 100)
        self.qualities = []
        self.whole_video = {}
        self.qualities_itag = {
            '144p': 394, '240p': 395, '360p': 396, '480p': 397, '720p': 398, '1080p': 399, '1440p': 308, '2160p': 315
        }
        self.muted = False
        self.close_player = 0

    def website_loader(self, video_url):
        self.browser.get(video_url)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'video')))
        self.browser.switch_to.window(self.browser.window_handles[0])

    def show_quality(self, showq=True):
        setting = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'ytp-settings-button')))
        setting.click()
        settings_menu = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'ytp-menuitem')))
        for option in settings_menu:
            if "Quality" in option.get_attribute('innerText'):
                option.click()
        quality_menu = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'ytp-menuitem')))
        self.qualities = []
        for quality in quality_menu:
            try:
                quality_text = quality.get_attribute('innerText')
                if re.match(r"(\d{3,4}p+)", quality_text):
                    self.qualities.append({'quality': quality_text.split(' ')[0], 'object': quality})
            except StaleElementReferenceException:
                continue

        for i in range(len(self.qualities)):
            quality_dict = self.qualities[i]
            if showq:
                print(f'{i}: {quality_dict.get("quality")}')

    def get_url(self, req_quality=-1):
        quality_object = self.qualities[int(req_quality)].get('object')
        quality_text = self.qualities[int(req_quality)].get('quality')
        quality_object.click()
        self.whole_video = {}
        while len(self.whole_video) < 2:
            logs = self.browser.get_log("performance")
            for entry in logs:
                log = json.loads(entry["message"])["message"]
                if "Network.response" in log["method"] or "Network.request" in log["method"] or "Network.webSocket" in \
                        log["method"]:
                    content_type = self.search(log, "content-type")
                    if content_type and ('video' in content_type or 'audio' in content_type):
                        url = self.search(log, 'url')
                        if url:
                            if 'video' in content_type:
                                if f"itag={self.qualities_itag[quality_text]}" in url:
                                    video = url.split('&range')[0]
                                    self.whole_video['video'] = video
                                else:
                                    continue
                            elif 'audio' in content_type:
                                if 'itag=251' in url:
                                    audio = url.split('&range')[0]
                                    self.whole_video['audio'] = audio
                                else:
                                    continue

    def search(self, dictionary, word):
        if word in dictionary:
            return dictionary[word]
        else:
            for v in dictionary:
                if type(dictionary[v]) is dict:
                    return self.search(dictionary[v], word)

    def toggle_mute(self, player):
        if self.muted:
            player.set_volume(1.0)
            self.muted = False
        else:
            player.set_volume(0)
            self.muted = True

    def close(self):
        self.close_player = 1

    def play_audio(self):
        tools.set_loglevel("quiet")
        player = MediaPlayer(self.whole_video['audio'], ff_opts={'vn': True, 'vs': True, 'loop': 0, 'autoexit': True})
        player.set_volume(0.8)
        keyboard.add_hotkey("alt+q", self.close)
        keyboard.add_hotkey("alt+m", self.toggle_mute, args=(player,))
        keyboard.add_hotkey("alt+p", player.toggle_pause)
        keyboard.add_hotkey("alt+down", lambda: player.set_volume((int(player.get_volume() * 100) - 10) / 100))
        keyboard.add_hotkey("alt+up", lambda: player.set_volume((int(player.get_volume() * 100) + 10) / 100))
        keyboard.add_hotkey("alt+right", lambda: player.seek(5))
        keyboard.add_hotkey("alt+left", lambda: player.seek(-5))
        os.system("cls")
        print("Controls:"
              "\n\tAlt+p: Pause/Play\n\tAlt+m: Mute\n\tAlt+Up Arrow: Volume Up\n\tAlt+Down Arrow: Volume Down\n\t"
              "Alt+Right Arrow: Seek Forward 5s\n\tAlt+Left Arrow: Seek Backward 5s\n\tAlt+q: Quit\n\n")
        while True:
            if self.close_player:
                player.close_player()
                keyboard.remove_all_hotkeys()
                break
            player.get_frame()
            while player.get_metadata()["duration"] is None:
                pass
            current_time = str(timedelta(seconds=player.get_pts())).split(".")[0]
            duration_time = str(timedelta(seconds=player.get_metadata()["duration"])).split(".")[0]
            progress_bar = int((player.get_pts() / player.get_metadata()["duration"]) * 50) * "-"
            status = "Playing" if not player.get_pause() else "Paused"
            print("{:>20} <{:50}>{:>10}/{:<10}Volume: {:<5}Muted: {:<20}".format(status, progress_bar, current_time,
                                                                                 duration_time,
                                                                                 int(player.get_volume() * 100),
                                                                                 self.muted), end="\r")

    def download(self):
        vid = VideoFileClip(self.whole_video['video'])
        aud = AudioFileClip(self.whole_video['audio'])
        final_vid = vid.set_audio(aud)
        final_vid.set_duration(aud.duration)
        final_vid.write_videofile('out.mp4')


if __name__ == '__main__':
    a = YoutubeDownloader()
    try:
        youtube_video_url = input('Youtube Url: ')
        a.website_loader(youtube_video_url)
        while True:
            try:
                os.system("cls")
                play_download = int(input("1: Download Video \n2: Play Audio\n3: Exit\n Enter Your Choice: "))
            except ValueError:
                print("Invalid Choice!")
                continue
            if play_download == 1:
                a.show_quality()
                download_quality = int(input('Quality: '))
                a.get_url(download_quality)
                a.download()
            elif play_download == 2:
                a.show_quality(False)
                a.get_url()
                a.play_audio()
            elif play_download == 3:
                break
            else:
                print("Invalid Choice")
    except Exception as e:
        print(e)
    finally:
        a.browser.quit()
