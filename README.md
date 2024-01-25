This is an archival tool that will eventually back up to a server and connect to a web interface. It is very much still in development.
<br/>
<br/>
If you want to try running it, main.py will go through all the posts within the last 24 hours on the sub it's pointed to. I have it pointing towards Myanmar Combat Footage, which is an NSFW sub.You can change that in scraper.py on this line:

`driver.get("https://www.reddit.com/r/Myanmarcombatfootage/new")`

I believe it will work the same on any sub.
<br/>
<br/>
**Watch out!** If you run main.py with the correct libraries, a window will pop up and start browsing that sub. It will bypass NSWF filters, so please be certain you are okay with blood and gore potentially popping up. If not, in scraper.py in `make_driver()` you can uncomment

`options = Options()`

`options.add_argument('--headless=new')`

`driver = webdriver.Chrome(service=service, options=options)`

and comment `driver = webdriver.Chrome(service=service)` to make the browser headless.
<br/>
<br/>
**Also!** This will download content automatically unless you comment out these four lines in `process_post_info()` in scraper.py:

`process_err = download_video(title, link)`

`errors.append(process_err)`

`process_err = download_gallery(title, gallery)`

`errors.append(process_err)`