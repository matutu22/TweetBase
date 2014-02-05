import couchdb
from couchdb.design import ViewDefinition


class TweetCouch(object):
	def __init__(self, dbname, url=None):
		try:
			self.server = couchdb.Server(url=url)
			self.db = self.server.create(dbname)
			self._create_views()
		except couchdb.http.PreconditionFailed:
			self.db = self.server[dbname]

	def _create_views(self):
		# twitter/count_type
		count_type_map = 'function(doc) { emit([doc.type, doc.id], 1); }'
		count_type_reduce = 'function(keys, values) { return sum(values); }'
		view = ViewDefinition('twitter', 'count_type', count_type_map, reduce_fun=count_type_reduce)
		view.sync(self.db)

		# twitter/get_tweets
		get_tweets = 'function(doc) { if (doc.type == "TWITTER_STATUS") emit(+doc.id, doc); }'
		view = ViewDefinition('twitter', 'get_tweets', get_tweets)
		view.sync(self.db)

		# twitter/get_users
		get_users = 'function(doc) { if (doc.type == "TWITTER_USER") emit(+doc.id, doc); }'
		view = ViewDefinition('twitter', 'get_users', get_users)
		view.sync(self.db)

	def tweet_count(self):
		for row in self.db.view('twitter/count_type', group=True, group_level=1,
		                        startkey=['TWITTER_STATUS'], endkey=['TWITTER_STATUS',{}]):
        		return row['value']
		return -1

	def user_count(self):
		for row in self.db.view('twitter/count_type', group=True, group_level=1,
		                        startkey=['TWITTER_USER'], endkey=['TWITTER_USER',{}]):
        		return row['value']
		return -1

	def prune(self, max_count):
		count = self.tweet_count()
		if count > max_count:
			for row in self.db.view('twitter/get_tweets', limit=count-max_count, descending=False):
				self.db.delete(self.db[row.id])

	def compact(self):
		self.db.compact()
		self.db.cleanup()

	def delete(self):
		self.server.delete(self.db.name)

	def _new_tweet_doc(self, tw):
		return {
			'_id':                     tw['id_str'],
			'type':                    'TWITTER_STATUS',
			'coordinates':             tw['coordinates']['coordinates'] if tw['coordinates'] else None,
			'created_at':              tw['created_at'],
			'entities':                tw['entities'],
			'favorite_count':          tw['favorite_count'],
			'id':                      tw['id_str'],
			'in_reply_to_screen_name': tw['in_reply_to_screen_name'],
			'in_reply_to_status_id':   tw['in_reply_to_status_id'],
			'in_reply_to_user_id':     tw['in_reply_to_user_id'],
			'lang':                    tw['lang'],
			'place':                   tw['place'],
			'retweet_count':           tw['retweet_count'],
			'retweeted_status_id':     tw['retweeted_status']['id_str'] if 'retweeted_status' in tw else None, # PARENT
			'retweeted_by_list':       [], # extra field containing id's of CHILD tweets
			'source':                  tw['source'],
			'text':                    tw['text'],
			'truncated':               tw['truncated'],
			'user_id':                 tw['user']['id_str']
		}

	def _new_user_doc(self, user):
		return {
			'_id':                     user['id_str'],
			'type':                    'TWITTER_USER',
			'created_at':              user['created_at'],
			'description':             user['description'],
			'entities':                user['entities'] if 'entities' in user else None,
			'favourites_count':        user['favourites_count'],
			'followers_count':         user['followers_count'],
			'friends_count':           user['friends_count'],
			'geo_enabled':             user['geo_enabled'],
			'id':                      user['id_str'],
			'lang':                    user['lang'],
			'location':                user['location'],
			'name':                    user['name'],
			'profile_image_url':       user['profile_image_url'],
			'screen_name':             user['screen_name'],
			'statuses_count':          user['statuses_count'],
			'url':                     user['url'],
			'utc_offset':              user['utc_offset'],
			'verified':                user['verified']
		}

	def save_tweet(self, tw, retweeted_by_id=None):
		doc = self.db.get(tw['id_str'])
		if not doc:
			if 'retweeted_status' in tw:
				self.save_tweet(tw['retweeted_status'], tw['id_str'])
			self.save_user(tw['user'])
			doc = self._new_tweet_doc(tw)
		if retweeted_by_id:
			doc['retweeted_by_list'].append(retweeted_by_id)
		self.db.save(doc)
		
	def save_user(self, user):
		if not self.db.get(user['id_str']):
			doc = self._new_user_doc(user)
			self.db.save(doc)