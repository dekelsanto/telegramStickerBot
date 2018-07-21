import os
import sys
import json
import time
import random
import urllib
import urllib2
import urlparse

BOT_ADDED_TO_CHAT = 0
BOT_REMOVED_FROM_CHAT = 1
CHAT_MESSAGES_RECEIVED = 2
NEXT_UPDATE_ID = 3
BOT_MENTIONED_IN_MESSAGE = 4

BOT_ID = 156655373
BOT_API_URL = "" # Fill your Telegram bot URL here
STICKER_FILE_ID = [] # Fill your sticker IDs here
BOT_AT_HANDLE = "@" # Fill your bot handle here

UPDATE_INTERVAL_IN_SECONDS = 10

class Chat:
	"""
	Represents a single chat room. Decides when to send a sticker randomly.
	  A list of these is held in the main function
	"""
	def __init__(self):
		self.messageCounter = 0
		self.thresholds = (50, 70)
		self.currentThreshold = random.randint(*self.thresholds)
	
	def getMessageCount(self):
		return self.messageCounter
	
	def getThreshold(self):
		return self.currentThreshold
	
	def getMessagesUntilSticker(self):
		return self.currentThreshold - self.messageCounter
	
	def incrementMessageCount(self, offset=1):
		self.messageCounter += offset
		
	def messageCountThresholdExceeded(self):
		return self.messageCounter >= self.currentThreshold
	
	def resetMessageCount(self):
		self.messageCounter = 0
		self.currentThreshold = random.randint(*self.thresholds)
		
class BotCommunicator:
	"""
	Serves as an abstraction to controlling the bot via HTTP GET/POST API. 
	"""
	def __init__(self):
		self.nextUpdateID = 0
		self.getUpdatesURL = urlparse.urljoin(BOT_API_URL, "/getUpdates")
		self.sendStickerURL = urlparse.urljoin(BOT_API_URL, "/sendSticker")
		
	def communicate(self, url, values):
		dataToSend = urllib.urlencode(values)
		request = urllib2.Request(url, dataToSend)
		try:
			response = urllib2.urlopen(request)
		except urllib2.URLError as e:
			print "\n\nError while communicating with bot!"
			print "URL: " + request.get_full_url()
			print e
			print "\n\nPress enter to close this window."
			raw_input()
			sys.exit()
		return response.read()
	
	def setNextUpdateID(self, nextUpdateID):
		self.nextUpdateID = nextUpdateID
	
	def getUpdates(self):
		getUpdatesValues = {"offset":self.nextUpdateID}
		return self.communicate(self.getUpdatesURL, getUpdatesValues)
		
	def sendSticker(self, chatID):
		sendStickerValues = {"chat_id":chatID, "sticker":random.choice(STICKER_FILE_ID)}
		self.communicate(self.sendStickerURL, sendStickerValues)
		
class UpdateElement:
	"""
	A generic node class, which keeps everything a bit more organized.
	  Not implemented using collections.namedtuple() because self.count 
	  has a default value, which is a pain in the arse with namedtuples
	"""
	def __init__(self, type, value, count=0):
		self.type = type
		self.value = value
		self.count = count
		
class UpdatesDecoder:
	"""
	Parses json replies from the Telegram servers, iterates over messages within, 
	  and creates a list of UpdateElement objects representing various events.
	"""
	def __init__(self):
		self.resetAggregators()
	
	def resetAggregators(self):
		self.currentHighestUpdateID = 0
		self.chatParticipantElements = []
		self.messageCountElements = {}
		self.chatsMentionedIn = {}
	
	def handleItem(self, item):
		if "message" in item:
			messageData = item["message"]
			chatID = messageData["chat"]["id"]
			
			if "new_chat_participant" in messageData and messageData["new_chat_participant"]["id"] == BOT_ID:
				self.chatParticipantElements.append(UpdateElement(type=BOT_ADDED_TO_CHAT, value=chatID))
			
			elif "left_chat_participant" in messageData and messageData["left_chat_participant"]["id"] == BOT_ID:
				self.chatParticipantElements.append(UpdateElement(type=BOT_REMOVED_FROM_CHAT, value=chatID))			
				
			else:
				if chatID in self.messageCountElements:
					self.messageCountElements[chatID].count += 1
				else:
					self.messageCountElements[chatID] = UpdateElement(type=CHAT_MESSAGES_RECEIVED, value=chatID, count=1)
					
				if "text" in messageData and BOT_AT_HANDLE in messageData["text"]:
					self.chatsMentionedIn[chatID] = UpdateElement(type=BOT_MENTIONED_IN_MESSAGE, value=chatID)
			
		if item["update_id"] > self.currentHighestUpdateID:
			self.currentHighestUpdateID = item["update_id"]

	def decodeUpdate(self, update):
		self.resetAggregators()
		parsedUpdate = json.loads(update)
		if not parsedUpdate["ok"]:
			return []
		for item in parsedUpdate["result"]:
			self.handleItem(item)
		
		returnElements = self.chatsMentionedIn.values() + self.chatParticipantElements + self.messageCountElements.values()
		if len(returnElements) > 0: # Then self.currentHighestUpdateID isn't zero anymore
			returnElements.append(UpdateElement(type=NEXT_UPDATE_ID, value=self.currentHighestUpdateID + 1))
	
		return returnElements
			
def flushUpdates(botCommunicator, updatesDecoder):
	"""
	Fresh start - consume all previous json updates sent to this bot
	  Wait until the bot sends empty jsons 10 times to be totally convinced
	"""
	timesZero = 0 
	while timesZero < 10:  
		updateElements = updatesDecoder.decodeUpdate(botCommunicator.getUpdates())
		if len(updateElements) == 0:
			timesZero += 1
		for element in updateElements:
			if element.type == NEXT_UPDATE_ID:
				botCommunicator.setNextUpdateID(element.value)
		time.sleep(1)
		
		
def main():
	chatList = {}
	botCommunicator = BotCommunicator()
	updatesDecoder = UpdatesDecoder() 	
	
	os.system("title Initializing...")
	print "Initializing..."
	flushUpdates(botCommunicator, updatesDecoder)
	
	os.system("title Telegram Sticker Bot Service")
	try:
		while True:
			# This could definitely be a bit cleaner
			updates = botCommunicator.getUpdates()
			updateElements = updatesDecoder.decodeUpdate(updates)
			for element in updateElements:
				if element.type == BOT_ADDED_TO_CHAT:
					chatList[element.value] = Chat()
					botCommunicator.sendSticker(element.value)
					
				elif element.type == BOT_REMOVED_FROM_CHAT:
					if element.value in chatList:
						del(chatList[element.value])
						
				elif element.type == CHAT_MESSAGES_RECEIVED:
					if not (element.value in chatList):
						chatList[element.value] = Chat()
					chatList[element.value].incrementMessageCount(element.count)
					if chatList[element.value].messageCountThresholdExceeded():
						chatList[element.value].resetMessageCount()
						botCommunicator.sendSticker(element.value)
						
				elif element.type == NEXT_UPDATE_ID:
					botCommunicator.setNextUpdateID(element.value)
					
				elif element.type == BOT_MENTIONED_IN_MESSAGE:
					botCommunicator.sendSticker(element.value)
					if element.value in chatList:
						chatList[element.value].incrementMessageCount(-1)
						
				else:
					continue
			
			os.system("cls")
			
			print "####################################"
			print "### Telegram Sticker Bot Service ###"
			print "####################################\n"
			
			if len(chatList) == 0:
				print "Bot is not in any active group chat."
			else:
				print "Active group(s):"
				for chatID in chatList.keys():
					print "\t* Chat ID {0}: {1}/{2} messages until next sticker".format(chatID, chatList[chatID].getMessageCount(), chatList[chatID].getThreshold())

			time.sleep(UPDATE_INTERVAL_IN_SECONDS)
	except KeyboardInterrupt:
		print "\nCtrl-C\nExiting!\n"
	
		
		
if __name__ == "__main__":
	main()
	