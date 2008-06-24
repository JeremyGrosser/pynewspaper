#!/usr/bin/python
import feedparser, sgmllib, sys, os, os.path, nntplib, time
from threading import Thread
from datetime import date

#print 'Content-type: text/html\n'
sys.stdout = file('/users/u13/synack/newspaper.log', 'w')
sys.stderr = sys.stdout

if len(sys.argv) < 2:
	print 'Usage: ' + sys.argv[0] + ' <feeds directory> <output file>'
	sys.exit(1)

def getNews(server, groups, user, password):
	news = nntplib.NNTP(server, 119, user, password)

	today = date.today()
	yearstr = str(today.year)[2:]
	if today.month < 10:	monthstr = '0' + str(today.month)
	else:					monthstr = str(today.month)
	if today.day < 10:		daystr = '0' + str(today.day - 4)
	else:					daystr = str(today.day - 4)
	yesterday = yearstr + monthstr + daystr

	newnews = {}
	articles = []
	groups = [groups]
	for group in groups:
		newnews[group] = news.newnews(group, yesterday, '000000')[1:]

	for group in newnews:
		news.group(group)
		for posts in newnews[group]:
			for post in posts:
				headers = news.head(post)[3]
				resp = news.body(post)
	
				status = resp[0]
				length = resp[1]
				id = resp[2]
				body = resp[3]
	
				fullbody = ''
				for line in body:
					fullbody += line + 'X*X\n'

				for header in headers:
					if header.startswith('Subject:'):	subject = header[9:]
					if header.startswith('From:'):		postfrom = header[6:]
					if header.startswith('Newsgroups:'):	groups = header[12:]
					if header.startswith('Date:'):		postdate = header
				articles.append((postfrom, subject, groups, fullbody, postdate))
	news.quit()
	return articles

class Stripper(sgmllib.SGMLParser):
	def __init__(self):
		sgmllib.SGMLParser.__init__(self)
		
	def strip(self, some_html):
		self.theString = ""
		self.feed(some_html)
		self.close()
		self.theString = self.theString.replace('<', '&lt;')
		self.theString = self.theString.replace('>', '&gt;')
		self.theString = self.theString.replace('/', '/&thinsp;')
		self.theString = self.theString.replace('X*X', '<br />')
		self.theString = self.theString.replace('\t', '&#09')
		#self.theString = self.theString.replace('\xb7', '-')

		newstring = ''
		for line in self.theString.splitlines():
			if not line.startswith('&gt;') and not line.find('wrote:') != -1 and not line == '<br />':
				newstring += line + '\n'
		return newstring
	
	def handle_data(self, data):
		try:
			self.theString += data
		except UnicodeDecodeError:
			pass

class feedGrabber(Thread):
	def __init__(self, url):
		Thread.__init__(self)
		self.url = url
		self.feed = 0
	def run(self):
		self.feed = feedparser.parse(self.url)

class pageBuilder(Thread):
	def __init__(self, feedname):
		Thread.__init__(self)
		self.feedname = feedname
	def run(self):
		buildPage(feedname)

def buildPage(feedname):
	try:
		print 'Building feed: ' + repr(feedname)

		feeds = []
		fd = open(sys.argv[1] + '/' + feedname, 'r')
		feeds += fd.read().split('\n')[:-1]
		fd.close()

		allentries = []
		page = ''
		fd = open('header.res', 'r')
		page += fd.read()
		fd.close()

		if feeds[0] == 'http':
			feeds = feeds[1:]

			months = ("January",
				"February",
				"March",
				"April",
				"May",
				"June",
				"July",
				"August",
				"September",
				"October",
				"November",
				"December")
		
			count = 0
			grabberlist = []
			for url in feeds:
				grabber = feedGrabber(url)
				grabberlist.append(grabber)
				grabber.start()
				#allentries += feedparser.parse(url).entries
	
			for grabber in grabberlist:
				grabber.join()
				print "\tGot ", grabber.url
				for entry in grabber.feed.entries:
					hours = entry.updated_parsed[3]
					hours = hours - 5
					if hours < 0:
						hours += 12
					if entry.updated_parsed[4] < 10:
						minutes = '0' + str(entry.updated_parsed[4])
					else:
						minutes = str(entry.updated_parsed[4])
					if hours > 12:
						hours = hours - 12
						ampm = 'pm'
					else:
						ampm = 'am'
					hours = str(hours)
					postdate = months[entry.updated_parsed[1] - 1] + ' ' + str(entry.updated_parsed[2]) + ', ' + str(entry.updated_parsed[0]) + ' - ' + hours + ':' + minutes + ampm
					allentries.append({'title': entry.title, 'link': entry.link, 'date': postdate, 'datearr': entry.updated_parsed, 'body': entry.description, 'subhead': postdate, 'source': 'feedparser'})
			allentries.sort(key=lambda x: x['datearr'], reverse=1)
		elif feeds[0] == 'nntp':
			feeds = feeds[1:]
			for group in feeds[1].split(', '):
				allnews = getNews(feeds[0], group, feeds[2], feeds[3])
				print "\tGot " + group + ' from ' + feeds[0]
				for post in allnews:
					try:
						body = post[3] + '\n'
						postdate = time.strptime(post[4][6:31], '%a, %d %b %Y %H:%M:%S')
					except ValueError:
						print "\t\tLame date string: " + post[4][6:]
						#postdate = (0, 1, 1, 0, 0, 0, 0, 1, 0)
						postdate = time.strptime(post[4][6:26], '%d %b %Y %H:%M:%S')
					allentries.append({'title': post[1], 'link': '#', 'subhead': post[0] + ' - ' + time.strftime("%B %d, %Y", postdate), 'date': postdate, 'body': body, 'source': 'nntp'})
			allentries.sort(key=lambda x: x['date'], reverse=1)

		onethird = len(allentries) / 3
		count = 0
		onethird += 1
	
		print "\tBuilding ", feedname
		st = Stripper()
		page += " <div class=\"column\">"
		for entry in allentries:
			entryhtml = ""
			if(count >= onethird):
				page += " </div>"
				page += " <div class=\"column\">"
				count = 0
	
			entryhtml += "  <span class=\"itemtitle\"><a href=\"" + entry['link'] + "\">" + entry['title'] + "</a></span>"
			entryhtml += "  <br /><span class=\"itemdate\">" + entry['subhead'] + "</span>"
			try:
				entryhtml += "  <p>" + st.strip(entry['body']) + "</p>"
			except sgmllib.SGMLParseError:
				print 'Error stripping body of post: ', entry['title']
			if entry['source'] != 'nntp':
				page += entryhtml.encode('utf-8', 'xmlcharrefreplace')
			else:
				page += entryhtml
			count += 1
	
		page += " </div>"
	
		fd = open('footer.res', 'r')
		page += fd.read()
	
		fd = open(os.path.basename(feedname) + '.html', 'w')
		fd.write(page)
		fd.close()
	except IOError:
		print feedname, ': ', sys.exc_value

builderlist = []
for feedname in os.listdir(sys.argv[1]):
	#builder = pageBuilder(feedname)
	#builder.start()
	#builderlist.append(builder)
	buildPage(feedname)

#for builder in builderlist:
#	builder.join()
