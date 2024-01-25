# Dependencies
from bs4 import BeautifulSoup as bs
import requests
from requests.exceptions import ConnectionError
from selenium import webdriver
import time
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import ffmpeg
import constants
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
# import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.common.keys import Keys

def make_driver():
    try:
        service = Service(ChromeDriverManager().install())
        
        driver = webdriver.Chrome(service=service)

        # options = Options()
        # options.add_argument('--headless=new')
        # driver = webdriver.Chrome(service=service, options=options)
        return driver
    except ConnectionError as e:
        print(e)

def check_within_day(dt):
    current_datetime = datetime.now()
    time_difference = current_datetime - dt
    if time_difference.total_seconds() < 86400:
        return True
    else:
        return False
    
def download(url, save_path, requests_session=None):
    if requests_session:
        # for testing
        response = requests_session.get(url, stream=True)
    else:
        response = requests.get(url, stream=True)
    # Check if the request was successful
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
    else:
        raise ConnectionError(f"couldn't find the video at {url}")

def get_details(result):
    flair = result.find('span', class_='bg-tone-4')
    if flair:
        flair_text = flair.text.split('\n')[1].strip()
    else:
        flair_text = "no flair"

    shreddit_post = bs(str(result).split('\n')[0], 'html.parser').find()
    timestamp = shreddit_post['created-timestamp']
    timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")
    score = shreddit_post.get('score', 'hidden')
    if score != 'hidden':
        score = int(score)
    
    post_type = shreddit_post['post-type']
    post_link = "https://www.reddit.com" + shreddit_post['permalink']
    content_link = shreddit_post['content-href']
    gallery = []
    if post_type == 'gallery':
        # should also get alternate text
        # is this the highest quality image?
        soup = bs(str(result), 'html.parser')
        imgs = soup.find_all('img')
        for img in imgs:
            if img['alt']:
                alt_text = img['alt'].strip('r/Myanmarcombatfootage - ')
                try:
                    gallery.append([img['src'], alt_text])
                except KeyError:
                    gallery.append([img['data-lazy-src'], alt_text])
    else:
        gallery = None

    details = {
        "author": shreddit_post['author'],
        "dt": timestamp.replace(tzinfo=None),
        "flair": flair_text,
        "title": shreddit_post['post-title'],
        "score": score,
        "post_link": post_link,
        "content_link": content_link,
        "gallery": gallery,
        "post_type": post_type
    }

    return details
    
def get_posts(driver):
    driver.get("https://www.reddit.com/r/Myanmarcombatfootage/new")
    # Get scroll height
    day_loaded = False
    num_results = 0
    post_info = []
    while not day_loaded:
        html = driver.page_source
        soup = bs(html, 'html.parser')
        # should skip past the already found posts instead
        results = soup.find_all('shreddit-post')
        for result in results[num_results:]:
            details = get_details(result)
            
            if not check_within_day(details['dt']):
                # not within past 24 hours
                day_loaded = True
                break
            else:
                # within past 24 hours
                post_info.append({**details})
        
        # get previous result length to skip past checked results
        num_results = len(results)
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
    return post_info

def post_text(tag):
    return 'data-post-click-location' in tag.attrs and tag['data-post-click-location'] == 'text-body'

def process_post_info(post_info, driver, output_path="process_post_output.txt"):
    errors = []
    for post in post_info:
        # print(f"\ncontent link: {post['content_link']}\n")
        driver.get(post['post_link'])
        # wait = WebDriverWait(driver, 5)
        im_over_18 = None
        try:
            shadow_host1 = driver.find_element(By.TAG_NAME, "shreddit-experience-tree")
            shadow_root1 = shadow_host1.shadow_root
            time.sleep(1)
            shadow_host2 = shadow_root1.find_element(By.CSS_SELECTOR, "div shreddit-async-loader xpromo-nsfw-bypassable-modal-desktop")
            shadow_root2 = shadow_host2.shadow_root
            time.sleep(1)
            im_over_18 = shadow_root2.find_element(By.ID, "secondary-button")
            im_over_18.click()
            time.sleep(1)
        except Exception as e:
            # need to split out the exceptions here
            with open(output_path, "w") as f:
                f.write(str(e))
                html = driver.page_source
                f.write(html)

        html = driver.page_source
        soup = bs(html, 'html.parser')
        result = soup.find('shreddit-post')
        if result:
            text_body = result.find(post_text)
            post['text'] = text_body.text.strip() if text_body else None
            print(post['text'])

        title = post['title']
        match post['post_type']:
            case 'video':
                link = post['content_link']
                # process_err = download_video(title, link)
                # errors.append(process_err)
            case 'gallery':
                gallery = post['gallery']
                # process_err = download_gallery(title, gallery)
                # errors.append(process_err)

    return post_info, errors

def download_video(title, link):
    # filter title of / here
    title = title.replace('/', '-')
    errors = []
    video_format = 720
    # video without audio
    try:
        video_720 = f'{link}/DASH_720.mp4?source=fallback'
        download(video_720, f'../downloads/{title}_video_720.mp4')
    except ConnectionError as e:
        try:
            video_format = 360
            video_360 = f'{link}/DASH_360.mp4?source=fallback'
            download(video_360, f'../downloads/{title}_video_360.mp4')
            errors.append({'title': title, 'link': link, 'error': e.args})
        except ConnectionError as e:
            raise ConnectionError(f'Video not found for {video_720} or {video_360}')
    
    time.sleep(1)

    # audio without video
    try:
        audio_128 = f'{link}/DASH_AUDIO_128.mp4'
        download(audio_128, f'../downloads/{title}_audio_128.mp4')
    except ConnectionError as e:
        raise ConnectionError(f'Audio not found for {audio_128}')

    join_audio_video(f'../downloads/{title}_audio_128.mp4', f'../downloads/{title}_video_{video_format}.mp4', f'../downloads/{title}_combined.mp4')
    return errors

def download_gallery(title, gallery):
    # filter title of / here
    title = title.replace('/', '-')
    errors = []
    for i, img in enumerate(gallery):                                                     
        print(f"this is a gallery image {i}!\n", img)
        try:
            download(img[0], f'../downloads/{title}_img_{i}.webp')
            webp_to_png(f'../downloads/{title}_img_{i}.webp', f'../downloads/{title}_{i}.png')
        except ConnectionError as e:
            errors.append({'title': title, 'link': img[0], 'error': e.args})
        
        time.sleep(1)

    return errors

# idk how to actually test this other than check the output path
def join_audio_video(audio_path, video_path, output_path):
    audio_file = ffmpeg.input(audio_path)
    video_file = ffmpeg.input(video_path)

    # Join the audio and video files
    output_file = ffmpeg.output(audio_file, video_file, f"{output_path}.mp4")

    # Start the conversion
    output_file.run()

# idk how to actually test this other than check the output path
def webp_to_png(input_webp, output_png_path):
    webp = ffmpeg.input(input_webp)
    png = webp.output(f"{output_png_path}.png")

    # Write the output file
    png.run()

class BackBlazeHandler:
    endpoint = constants.endpoint
    key_id = constants.key_id
    application_key = constants.application_key
    download_directory = constants.download_directory
    bucket_name = constants.bucket_name

    # Delete the specified objects from B2
    def delete_files(self, keys, b2):
        objects = []
        for key in keys:
            objects.append({'Key': key})
        try:
            b2.Bucket(self.bucket_name).delete_objects(Delete={'Objects': objects})
        except ClientError as ce:
            print('error', ce)

    # Delete the specified object from B2 - all versions
    def delete_files_all_versions(self, keys, client):
        objects = []
        for key in keys:
            objects.append({'Key': key})
        try:
            # SOURCE re LOGIC FOLLOWING:  https://stackoverflow.com/questions/46819590/delete-all-versions-of-an-object-in-s3-using-python
            paginator = client.get_paginator('list_object_versions')
            response_iterator = paginator.paginate(Bucket=self.bucket_name)
            for response in response_iterator:
                versions = response.get('Versions', [])
                versions.extend(response.get('DeleteMarkers', []))
                for version_id in [x['VersionId'] for x in versions
                                if x['Key'] == key and x['VersionId'] != 'null']:
                    print('Deleting {} version {}'.format(key, version_id))
                    client.delete_object(Bucket=self.bucket_name, Key=key, VersionId=version_id)

        except ClientError as ce:
            print('error', ce)

    # Download the specified object from B2 and write to local file system
    def download_file(self, download_path, key_name, b2):
        try:
            b2.Bucket(self.bucket_name).download_file(key_name, download_path)
        except ClientError as ce:
            print('error', ce)

    # Return a boto3 client object for B2 service
    def get_b2_client(self):
            b2_client = boto3.client(service_name='s3',
                                    endpoint_url=self.endpoint,                # Backblaze endpoint
                                    aws_access_key_id=self.key_id,              # Backblaze keyID
                                    aws_secret_access_key=self.application_key) # Backblaze applicationKey
            return b2_client

    # Return a boto3 resource object for B2 service
    def get_b2_resource(self):
        b2 = boto3.resource(service_name='s3',
                            endpoint_url=self.endpoint,                # Backblaze endpoint
                            aws_access_key_id=self.key_id,              # Backblaze keyID
                            aws_secret_access_key=self.application_key, # Backblaze applicationKey
                            config = Config(signature_version='s3v4')
        )
        return b2

    # List the keys of the objects in the specified bucket
    def list_object_keys(self, b2):
        try:
            response = b2.Bucket(self.bucket_name).objects.all()

            return_list = []               # create empty list
            for object in response:        # iterate over response
                return_list.append(object.key) # for each item in response append object.key to list
            return return_list             # return list of keys from response

        except ClientError as ce:
            print('error', ce)


    # List browsable URLs of the objects in the specified bucket - Useful for *PUBLIC* buckets
    def list_objects_browsable_url(self, b2):
        try:
            bucket_object_keys = self.list_object_keys(b2)

            return_list = []                # create empty list
            for key in bucket_object_keys:  # iterate bucket_objects
                url = f"{self.endpoint}/{self.bucket_name}/{key}" # format and concatenate strings as valid url
                return_list.append(url)     # for each item in bucket_objects append value of 'url' to list
            return return_list              # return list of keys from response

        except ClientError as ce:
            print('error', ce)


    # Upload specified file into the specified bucket
    def upload_file(self, file_path, file_name, b2):
        try:
            response = b2.Bucket(self.bucket_name).upload_file(file_path, file_name)
        except ClientError as ce:
            print('error', ce)

        return response

    # # Call function to return reference to B2 service
    # b2 = get_b2_resource()

    # # Call function to return reference to B2 service
    # b2_client = get_b2_client()

    # bucket_object_keys = list_object_keys(b2)

    # # Call function to return list of object 'keys' formatted into friendly urls
    # browsable_urls = list_objects_browsable_url(b2)

    # # 06 - DOWNLOAD FILE
    # download_file("", "hello", b2)

    # # 21 - UPLOAD FILE
    # response = upload_file(f"{download_directory}/file", "name", b2)