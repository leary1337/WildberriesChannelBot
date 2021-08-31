#!/usr/bin/env python3
#-*- coding: UTF 8 -*-
from config import *

from telegram.utils.request import Request
from telegram import Update
from telegram import Bot
from telegram import ParseMode
from telegram.ext import Updater
from telegram.ext import Filters
from time import sleep
import time
import bs4
import requests
import logging
import collections

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('wb')

ParseResult = collections.namedtuple(
	'ParseResult',
	(
		'brand_name',
		'goods_name',
		'url',
		'price_old', 
		'lower_price',
		'img'
	),
)

LINKS = []

class ParseWB:
	"""Парсинг сайта Wildberries на товары по категориям"""
	def __init__(self):
		self.session = requests.Session()
		self.session.headers = {
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36 OPR/68.0.3618.112',
			'Accept-Language': 'ru',
		}
		self.result = []

	def load_page(self, source_url):
		url = source_url
		res = self.session.get(url=url)
		res.raise_for_status()
		return res.text

	def parse_page(self, text: str):
		soup = bs4.BeautifulSoup(text, 'lxml')
		container = soup.select('div.dtList.i-dtList.j-card-item')
		count = 0
		for block in container:
			if count == COUNT_ITEMS:
				break
			checker = self.parse_block(block=block)
			if checker == 1:
				continue
			else:
				count += 1

	def parse_block(self, block):
		url_block = block.select_one('a.ref_goods_n_p')
		if not url_block:
			logger.error('no url_block')
			return 1

		url = url_block.get('href')
		if not url:
			logger.error('no href')
			return 1

		# проверка был ли такой товар уже отправлен
		checker = self.check_items(url=url)
		if checker:
			return 1

		img_block = block.select_one('img.thumbnail')
		if not img_block:
			logger.error('no img_block')
			return 1

		img = img_block.get('src')
		if not img:
			logger.error('no img')
			return 1

		name_block = block.select_one('div.dtlist-inner-brand-name')
		if not name_block:
			logger.error(f'no name_block on {url}')
			return 1

		brand_name = name_block.select_one('strong.brand-name')
		if not brand_name:
			logger.error(f'no brand_name on {url}')
			return 1

		# Wrangler /
		brand_name = brand_name.text
		brand_name = brand_name.replace('/', '').strip()

		goods_name = name_block.select_one('span.goods-name')
		if not goods_name:
			logger.error(f'no goods_name on {url}')
			return 1
		goods_name = goods_name.text.strip()

		price_block = block.select_one('div.j-cataloger-price')
		if not price_block:
			logger.error(f'no price_block on {url}')
			return 1

		lower_price = price_block.select_one('ins.lower-price')
		if not lower_price:
			logger.error(f'no lower_price on {url}')
			return 1
		lower_price = lower_price.text.strip()

		price_old = price_block.select_one('span.price-old-block')
		if not price_old:
			logger.error(f'no price_old on {url}')
			return 1
		price_old = price_old.text.strip()

		self.result.append(ParseResult(
			url=url,
			brand_name=brand_name,
			goods_name=goods_name,
			price_old=price_old, 
			lower_price=lower_price,
			img=img,
		))

		logger.debug('%s, %s, %s, %s, %s', url, brand_name, goods_name, price_old, lower_price)
		logger.debug('-' * 100)

	def check_items(self, url):
		with open('data_articles.txt', 'r') as file_items:
			article_item = url.split('g/')[1].split('/')[0]
			check = 0
			for line in file_items.read().splitlines():
				if article_item == line:
					check = 1
					break
				else:
					continue
		if check == 1:
			return 1
		elif check == 0:
			with open('data_articles.txt', 'a') as file_items:
				file_items.write(article_item + '\n')
		return 0

	def run(self, source_url):
		for page in range(1, MAX_PAGES):
			try:
				text = self.load_page(source_url=source_url + '&page=' + str(page))
			except:
				try:
					text = self.load_page(source_url=source_url)
				except:
					break
			self.parse_page(text=text)
			if len(self.result) == COUNT_ITEMS:
				break
		logger.info(f'Получили {len(self.result)} элементов')
		return self.result

class ParseLinks(ParseWB):
	"""Парсинг сайта Wildberries на получение ссылок категорий"""
	def __init__(self):
		super().__init__()

	def load_page(self, source_url):
		url = source_url
		res = self.session.get(url=url)
		res.raise_for_status()
		return res.text

	def parse_page(self, text: str):
		soup = bs4.BeautifulSoup(text, 'lxml')
		container = soup.select('div.banner-container')
		count = 0
		for block in container:
			if count == COUNT_LINKS_CATEGORY:
				break;
			checker = self.parse_block(block=block)
			if checker == 1:
				continue
			else:
				count += 1

	def parse_block(self, block):
		link_block = block.select_one('a.j-banner-shown-stat.j-banner-click-stat.j-banner')
		if not link_block:
			logger.error('no link_block')
			return 1
		link = link_block.get('href')
		if not link:
			logger.error('no link')
			return 1

		self.result.append('https://www.wildberries.ru'+link)

	def run(self, source_url):
		text = self.load_page(source_url=source_url)
		self.parse_page(text=text)
		logger.info(f'Получили {len(self.result)} ссылок')
		return self.result
	
class ExportBot:
	"""Auto-channel bot telegram for Wildberries"""

	def __init__(self):
		self.chat_id = TELEGRAM_CHAT_ID
		self.request = Request(
			connect_timeout=0.5,
			read_timeout=60.0,
		)
		self.bot = Bot(
			token=TOKEN_BOT,
			request=self.request,
			# base_url='https://telegg.ru/orig/bot',
		)
		self.updater = Updater(
			bot=self.bot,
			use_context=True,
		)
		self.src = ParseWB()

	def public_posts(self):
		get_links = ParseLinks()
		LINKS = get_links.run(source_url=URL_PROMOTIONS)
		
		for link in LINKS:
			for_publishing = self.src.run(source_url=link)
			
			for post in for_publishing:
				new_price_old = post.price_old.split('-')[0]
				discount = post.price_old.split('-')[1]
				img = 'https:'+post.img
				text = f'<i>{post.brand_name}</i> / <b>{post.goods_name}</b>\n\n❌ <s>{new_price_old}</s>\n🎁 СКИДКА: -{discount}\n<b>🔥 {post.lower_price} 🔥</b>\n\n<a href="{post.url}">ССЫЛКА НА ТОВАР</a>'
				self.bot.sendPhoto(chat_id=self.chat_id, photo=img, caption=text, parse_mode=ParseMode.HTML)
				# Спим 20 секунд перед отправкой следующего поста
				time.sleep(20)
			for_publishing.clear()
			time.sleep(7200) # 2 часа

if __name__ == '__main__':
	runner = ExportBot()
	runner.public_posts()

