# Generated by Selenium IDE
import pytest
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from scripts.scraper import make_driver, check_within_day, download, get_details, download_video
import requests
from datetime import datetime, timedelta
import os
from urllib.request import url2pathname
from bs4 import BeautifulSoup as bs
from requests.exceptions import ConnectionError

url = "https://www.reddit.com/r/Myanmarcombatfootage/new"

@pytest.fixture
def driver():
    driver = make_driver()
    return driver

@pytest.fixture
def results():
    with open("tests/output.txt") as html:
        soup = bs(html, 'html.parser')
        results = soup.find_all('shreddit-post')
    return results

class LocalFileAdapter(requests.adapters.BaseAdapter):
    """Protocol Adapter to allow Requests to GET file:// URLs
    written by ssokolow at https://stackoverflow.com/questions/10123929/fetch-a-file-from-a-local-url-with-python-requests
    """

    @staticmethod
    def _chkpath(method, path):
        """Return an HTTP status for the given filesystem path."""
        if method.lower() in ('put', 'delete'):
            return 501, "Not Implemented"  # TODO
        elif method.lower() not in ('get', 'head'):
            return 405, "Method Not Allowed"
        elif os.path.isdir(path):
            return 400, "Path Not A File"
        elif not os.path.isfile(path):
            return 404, "File Not Found"
        elif not os.access(path, os.R_OK):
            return 403, "Access Denied"
        else:
            return 200, "OK"

    def send(self, req, **kwargs):  # pylint: disable=unused-argument
        # Return the file specified by the given request
        path = os.path.normcase(os.path.normpath(url2pathname(req.path_url)))
        response = requests.Response()

        response.status_code, response.reason = self._chkpath(req.method, path)
        if response.status_code == 200 and req.method.lower() != 'head':
            try:
                response.raw = open(path, 'rb')
            except (OSError, IOError) as err:
                response.status_code = 500
                response.reason = str(err)

        if isinstance(req.url, bytes):
            response.url = req.url.decode('utf-8')
        else:
            response.url = req.url

        response.request = req
        response.connection = self

        return response

    def close(self):
        pass


def test_connection():
    # check that the main site is up
    response = requests.get(url)
    assert response.status_code == 200
    # should check that content is also up
    # response.html?

def test_check_within_day_true():
    # should return True as is within past 24 hours
    current_datetime = datetime.now()
    edge_of_today = current_datetime - timedelta(hours=23)
    assert check_within_day(edge_of_today)

def test_check_within_yesterday():
    # should return False as is outside of past 24 hours
    current_datetime = datetime.now()
    edge_of_yesterday = current_datetime - timedelta(hours=25)
    assert not check_within_day(edge_of_yesterday)

def check_within_tomorrow():
    # should return False as is outside of past 24 hours
    current_datetime = datetime.now()
    edge_of_yesterday = current_datetime + timedelta(hours=1)
    assert not check_within_day(edge_of_yesterday)

def test_download_good():
    requests_session = requests.session()
    requests_session.mount('file://', LocalFileAdapter())
    # should download these files correctly
    url = f"file://{os.getcwd()}/downloads/Footage of BPLA(Bamar People's Liberation Army) troops fighting under the MNDAA during the battles in the Kokang region._audio_128.mp4"
    save_path = "to_delete_audio.mp4"
    download(url, save_path, requests_session)
    # assert the audio file exists
    assert "to_delete_audio.mp4" in os.listdir()
    
    url = f"file://{os.getcwd()}/downloads/Footage of BPLA(Bamar People's Liberation Army) troops fighting under the MNDAA during the battles in the Kokang region._video_360.mp4"
    save_path = "to_delete_video.mp4"
    download(url, save_path, requests_session)
    # assert the video file exists
    assert "to_delete_video.mp4" in os.listdir()

def test_download_bad():
    requests_session = requests.session()
    requests_session.mount('file://', LocalFileAdapter())
    # bad url
    url = f"file://{os.getcwd()}/tests/test_video.mp4"
    save_path = "hopefully_nonexistent.mp4"
    with pytest.raises(ConnectionError) as e:
        download(url, save_path, requests_session)
    # assert the file does not exist
    assert save_path not in os.listdir()
    # find ConnectionError
    assert e.value.args[0] == f"couldn't find the video at {url}"

# should add one that checks response.iter_content to see if everything is downloaded

def test_get_details_text(results):
    details = get_details(results[0])
    assert details['author'] == 'Most-Butterscotch871'
    assert details['dt'] == datetime(2023, 2, 17, 14, 21, 46, 343000)
    assert details['flair'] == 'Announcement 📣'
    assert details['title'] == 'General Personal Security (PERSEC) Rule'
    assert details['score'] == 31
    assert details['content_link'] == "https://www.reddit.com/r/Myanmarcombatfootage/comments/114lml4/general_personal_security_persec_rule/"
    assert details['post_type'] == 'text'

def test_get_details_no_score_link(results):
    details = get_details(results[1])
    print(details["content_link"])
    assert details['score'] == "hidden"
    # beautiful soup will fix the html to this link, which should have & in it after KARANG instead of &amp;
    assert details['content_link'] == "https://www.bbc.com/news/world-asia-65906961?at_campaign=KARANGA&at_medium=RSS"
    assert details['post_type'] == 'link'

def test_get_details_video(results):
    details = get_details(results[2])
    assert details['score'] == 15
    assert details['content_link'] == 'https://v.redd.it/2mrpu3m1w8pb1'
    assert details['post_type'] == 'video'
    assert details['flair'] == 'PDF'
    assert details['title'] == 'Myanmar military column entered Myaung region, Ayeyarwady, recently. They were faced by Anti-Junta forces belonging to the CDSOM. The battle lasted 5 hours, and casualties are unknown.'

def test_download_video_error(results):
    # should expand the scope to cover the invalid 720 but valid 360 case
    # also to broaden into: audio
    details = get_details(results[3])
    link = details['content_link']
    video_720 = f'{link}/DASH_720.mp4?source=fallback'
    video_360 = f'{link}/DASH_360.mp4?source=fallback'
    with pytest.raises(ConnectionError) as e:
        download_video(details['title'], link)
    
    assert e.value.args[0] == f'Video not found for {video_720} or {video_360}'