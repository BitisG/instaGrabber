from selenium import webdriver 
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import os
from os import path as os_path
import io
from PIL import Image
import requests
import hashlib
import piexif


image_post_xpath = '//div[@class="_97aPb   wKWK0"]//div[@class="KL4Bh"]'
album_post_xpath = '//div[@class="_97aPb   wKWK0"]//ul[@class="vi798"]'
video_post_xpath = '//div[@class="_97aPb   wKWK0"]//div[@class="_5wCQW"]'

options = Options()
## Enable/disable headless 
options.headless = False
options.add_argument('--window-size=1920,1080')
## Specify geckodriver path
DRIVER_PATH = 'CHANGE ME'
service = Service(DRIVER_PATH)
driver = webdriver.Firefox(options=options, service=service)

email = 'CHANGE ME'
with open('password.txt', 'r') as f:
	passwd = f.readlines()

with open('acc_urls.txt', 'r') as url_file:
	acc_urls = url_file.readlines()



def exists_by_xpath(xpath):
	try:
		driver.find_element(By.XPATH, xpath)
	except NoSuchElementException:
		return False
	return True

def add_exif(path, comment):
	img = Image.open(path)
	exif_ifd = {piexif.ExifIFD.UserComment: comment.encode('utf-8')}
	exif_dict = {"0th": {}, "Exif": exif_ifd, "1st": {}, "thumbnail": None, "GPS": {}}

	exif_dat = piexif.dump(exif_dict)
	img.save(path,  exif=exif_dat)


def rename(path, acc):
	with open(path, 'rb') as f:
		file_hash = hashlib.md5()
		chunk = f.read(8192)
		while chunk:
			file_hash.update(chunk)
			chunk = f.read(8192)
	new_path = f'CHANGE ME/{acc}/' + file_hash.hexdigest() + '.jpg'
	if not os_path.exists(new_path): #if file does not exist, create rename it
		os.rename(path, new_path)
	else: #Delete the temp file 
		os.remove(path)




def download(src, acc):
	base_dir = 'CHANGE ME'
	acc_dir = base_dir + f'/{acc}'
	os.makedirs(acc_dir, exist_ok = True)
	os.chdir(acc_dir)

	file_name = f'temp.jpg'

	try:
		image_content = requests.get(src).content
	except Exception as e:
		print(f'ERROR - download failed for src: {src} with exception: {e}')

	try:
		image_file = io.BytesIO(image_content)
		image = Image.open(image_file).convert('RGB')

		file_path = os.path.join(acc_dir, file_name)

		with open(file_path, 'wb') as f:
			image.save(f, 'JPEG', quality = 85)
		
		print('saving done, adding exif')

	except Exception as e:
		print(f'ERROR - could not save {src} - {e}')

	try:
		comment = driver.find_element(By.XPATH, './/span[@class="_7UhW9   xLCgt      MMzan   KV-D4           se6yk       T0kll "]').text
		add_exif(file_path, comment)
		print('added exif, renaming')
	except NoSuchElementException:
		print('No author comment, skipping exif step')

	rename(file_path, acc)
	print('renaming done, next picture: \n ----------------||----------------')

	'''
	do the whole insertion of metadata and renaming here.
	'''



def scrape_album(url, acc):
	length_of_album = len(driver.find_elements(By.XPATH, './/div[@class="Yi5aA "]'))
	image_src = []

	try:
		comment = driver.find_element(By.XPATH, './/span[@class="_7UhW9   xLCgt      MMzan   KV-D4           se6yk       T0kll "]').text
	except NoSuchElementException:
		comment = ''

	has_run = False
	for i in range(length_of_album):
		images_in_post = driver.find_elements(By.XPATH, './/li[@class="Ckrof"]//img[@class="FFVAD"]')
		if not has_run:
			for image in images_in_post:
				image_src.append(image.get_attribute('src'))
			has_run = True
		else:
			is_scraped = False
			new_image = images_in_post[-1]
			for src in image_src:
				if new_image.get_attribute('src') == src:
					is_scraped = True
			if not is_scraped:
				image_src.append(new_image.get_attribute('src'))


		driver.find_element(By.XPATH, './/button[@class="  _6CZji    "]').click()

	amount = len(image_src)	
	print(f'Found {amount} image posts in album, downloading:')
	for src in image_src:
		#Call download function on image
		download(src, acc)


def get_posts(acc_url):
	driver.get(acc_url)
	SCROLL_PAUSE_TIME = 2
	list_of_posts = driver.find_elements(By.XPATH, './/div[@class="v1Nh3 kIKUG _bz0w"]')
	# Get scroll height
	last_height = driver.execute_script("return document.body.scrollHeight")
	hrefs = set()
	for post in list_of_posts:
		hrefs.add(post.find_element(By.XPATH, './/a[1]').get_attribute('href'))

	while True:
		# Scroll down to bottom
		driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

		# Wait to load page
		sleep(SCROLL_PAUSE_TIME)

		# Calculate new scroll height and compare with last scroll height
		new_height = driver.execute_script("return document.body.scrollHeight")
		if new_height == last_height:
			break
		last_height = new_height

		list_of_posts.extend(driver.find_elements(By.XPATH, './/div[@class="v1Nh3 kIKUG _bz0w"]')[-12:])

		#Everytime we scroll down, 4 more rows of posts are added to the DOM, meaning we need to load 4*3=12 more posts 
		for post in list_of_posts[-12:]:
			hrefs.add(post.find_element(By.XPATH, './/a[1]').get_attribute('href'))

		if len(list_of_posts) >= 60:
			break

	print(f'{len(list_of_posts)} posts found. Commencing scrape')
	return hrefs



def scrape_ini(post_url, account):
	driver.get(post_url)
	sleep(1)

	#Getting element twice in case of succes, we can do better
	if exists_by_xpath(album_post_xpath):
		print(f'[+] found album post at {post_url}')
		post = driver.find_element(By.XPATH, album_post_xpath)
		album_posts = driver.find_elements(By.XPATH, './/div[@class="Yi5aA "]')
		scrape_album(post_url, account)
		#find_all_images

	elif exists_by_xpath(image_post_xpath):
		print(f'[+] found image post at {post_url}')
		post = driver.find_element(By.XPATH, image_post_xpath)
		image = post.find_element(By.XPATH, './/img[@class="FFVAD"]')
		src = image.get_attribute('src')
		download(src, account)
		#find_single_image
		#Call download function

	elif exists_by_xpath(video_post_xpath):
		print(f'[+] found video post at {post_url}, skipping \n')
		#Do nothing


def main():
	driver.get('https://www.instagram.com/accounts/login/?next=%2F&source=logged_out_half_sheet')
	sleep(0.5)

	#Cookie banner
	WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[text()="Only allow essential cookies"]'))).click()

	login = driver.find_element(By.XPATH, "//input[@name='username']").send_keys(email)
	password = driver.find_element(By.XPATH, "//input[@name='password']").send_keys(passwd[0])
	submit = driver.find_element(By.XPATH, "//button[@type='submit']")
	print('Logging in, please wait...')

	#Wait for cookie popup to go away, then click submit button to login
	#Change to WebDriverWait
	sleep(5)
	submit.click()

	#do not save password info
	WebDriverWait(driver,10).until(EC.element_to_be_clickable((By.XPATH, '//button[text()="Not Now"]'))).click()

	for acc in acc_urls:
		href = []
		post_url = []
		#Go to an account, get the posts, and then the links to the specific posts
		'''posts = get_posts(acc.strip())

		for post in posts:
			href.append(post.find_element(By.XPATH, './/a[1]'))

		for element in href:
			post_url.append(element.get_attribute('href'))'''

		post_url = get_posts(acc.strip())
		acc_name = acc.strip().split('/')[3]
		print(f'scraping profile {acc_name}')
		for url in post_url:
			#Each post has a href that links to a specific post only instead of a feed 
			scrape_ini(url, acc_name)

		print(f'Scraping of profile {acc} done \n')

	print('Job done! Shutting down...')
	## close the webdriver
	driver.quit()


if __name__ == '__main__':
	main()

#TODO: Support downloads of videos, maybe via youtube-dl