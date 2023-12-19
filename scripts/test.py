import scraper
from bs4 import BeautifulSoup as bs
html = ""
with open("maybe_just_a_rumor.txt", "r") as f:
    html = f.read()
driver = scraper.make_driver()
soup = bs(html, 'html.parser')
results = soup.find_all('shreddit-post')
data = scraper.get_details(results[0])
print(data)
post, errors = scraper.process_post_info([data], driver)
driver.quit()
print(post)