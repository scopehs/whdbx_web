import datetime
import pickle
import threading

# external modules
import cherrypy
import cherrypy.lib.sessions
import redis


class WhdbxRedisSession(cherrypy.lib.sessions.Session):

    locks = {}

    def __init__(self, id=None, **kwargs):
        """
        Called by internals of CherryPy
        :param id:
        :param kwargs: Redis backend supports the following parameters:
            'host' - where redis server runs, optional (localhost)
            'port' - port to connect to, optional (6379)
            'db' - Redis database number, optional (0)
        """
        self.redis_db = 0
        self.redis_host = 'localhost'
        self.redis_port = 6379
        # get params from kwargs
        if 'host' in kwargs:
            self.redis_host = kwargs['host']
        if 'port' in kwargs:
            self.redis_port = kwargs['port']
        if 'db' in kwargs:
            self.redis_db = kwargs['db']

        cherrypy.lib.sessions.Session.__init__(self, id=id, **kwargs)

        self._redis = redis.StrictRedis(self.redis_host, self.redis_port, self.redis_db)
        self.SESSION_PREFIX = 'cpsession_'

    def clean_up(self):
        """Clean up expired sessions."""
        # actually, it needs to do nothing, because Redis removes old data automatically.
        pass

    def _exists(self):
        return self._redis.exists(self.SESSION_PREFIX + str(self.id))

    def _load(self):
        # return value is assigned to _data member in a base class
        val = self._redis.get(self.SESSION_PREFIX + str(self.id))
        if val is not None:
            return pickle.loads(val)
        return None

    def _save(self, expiration_time: datetime.datetime):
        """
        Saves session in DB
        :param expiration_time: literally it is datetime.now() + datetime.timedelta(seconds=session.timeout * 60)
        :return: None
        """
        expires_in_timedelta = expiration_time - datetime.datetime.now()
        expires_in_seconds = expires_in_timedelta.total_seconds()
        # cherrypy session base classs stores all info in _data member
        val = pickle.dumps(self._data)
        # Save pickled value in Redis, together with its expiration time
        # 'ex' sets an expire flag on key for ex seconds.
        self._redis.set(self.SESSION_PREFIX + str(self.id), val, ex=expires_in_seconds)

    def _delete(self):
        self._redis.delete(self.SESSION_PREFIX + str(self.id))

    def acquire_lock(self):
        """Acquire an exclusive lock on the currently-loaded session data."""
        self.locks.setdefault(self.id, threading.RLock()).acquire()
        self.locked = True

    def release_lock(self):
        """Release the lock on the currently-loaded session data."""
        self.locks[self.id].release()
        self.locked = False

    def __len__(self):
        """Return the number of active sessions."""
        saved_session_names = self._redis.keys(self.SESSION_PREFIX + '*')
        return len(saved_session_names)