# -*- coding: utf-8 -*-

from gluon.custom_import import track_changes; track_changes(True) # for reloading modules

#########################################################################
## This scaffolding model makes your app work on Google App Engine too
## File is released under public domain and you can use without limitations
#########################################################################

## if SSL/HTTPS is properly configured and you want all HTTP requests to
## be redirected to HTTPS, uncomment the line below:
# request.requires_https()

if not request.env.web2py_runtime_gae:
    ## if NOT running on Google App Engine use SQLite or other DB
    db = DAL('sqlite://storage.sqlite')
else:
    ## connect to Google BigTable (optional 'google:datastore://namespace')
    db = DAL('google:datastore')
    ## store sessions and tickets there
    session.connect(request, response, db=db)
    ## or store session in Memcache, Redis, etc.
    ## from gluon.contrib.memdb import MEMDB
    ## from google.appengine.api.memcache import Client
    ## session.connect(request, response, db = MEMDB(Client()))

## by default give a view/generic.extension to all actions from localhost
## none otherwise. a pattern can be 'controller/function.extension'

# Luca says: do NOT make generic json possible, as there is information that should
# not leak out in most forms.
response.generic_patterns = ['*'] if request.is_local else []

## (optional) optimize handling of static files
# response.optimize_css = 'concat,minify,inline'
# response.optimize_js = 'concat,minify,inline'

#########################################################################
## Here is sample code if you need for
## - email capabilities
## - authentication (registration, login, logout, ... )
## - authorization (role based authorization)
## - services (xml, csv, json, xmlrpc, jsonrpc, amf, rss)
## - old style crud actions
## (more options discussed in gluon/tools.py)
#########################################################################

from gluon.tools import Auth, Crud, Service, PluginManager, prettydate
auth = Auth(db)
crud, service, plugins = Crud(db), Service(), PluginManager()

## create all tables needed by auth if not custom tables
auth.define_tables(username=False)

## configure email
mail = auth.settings.mailer
mail.settings.server = 'logging' or 'smtp.gmail.com:587'
mail.settings.sender = 'you@gmail.com'
mail.settings.login = 'username:password'

## configure auth policy
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.settings.reset_password_requires_verification = True

##### This tells web2py to use GAE logins.
if request.env.web2py_runtime_gae:
    from gluon.contrib.login_methods.gae_google_account import GaeGoogleAccount
    auth.settings.login_form = GaeGoogleAccount()
    auth.settings.actions_disabled.append('request_reset_password')
    auth.settings.actions_disabled.append('reset_password')
    auth.settings.actions_disabled.append('retrieve_password')
    auth.settings.actions_disabled.append('email_reset_password')
    auth.settings.actions_disabled.append('change_password')
    auth.settings.actions_disabled.append('retrieve_username')
    auth.settings.actions_disabled.append('verify_email')
    auth.settings.actions_disabled.append('register')
    auth.settings.actions_disabled.append('profile')
    db.auth_user.email.writable = False

#### How to get an email address.
def get_user_email():
    """Note that this function always returns a lowercase email address."""
    if request.env.web2py_runtime_gae:
        from google.appengine.api import users as googleusers
        u = googleusers.get_current_user()
        if u is None:
            return None
        else:
            return u.email().lower()
    else:
        if auth.user is None:
            return None
        else:
            return auth.user.email.lower()

## if you need to use OpenID, Facebook, MySpace, Twitter, Linkedin, etc.
## register with janrain.com, write your domain:api_key in private/janrain.key
from gluon.contrib.login_methods.rpx_account import use_janrain
use_janrain(auth, filename='private/janrain.key')

#########################################################################
## Define your tables below (or better in another model file) for example
##
## >>> db.define_table('mytable',Field('myfield','string'))
##
## Fields can be 'string','text','password','integer','double','boolean'
##       'date','time','datetime','blob','upload', 'reference TABLENAME'
## There is an implicit 'id integer autoincrement' field
## Consult manual for more options, validators, etc.
##
## More API examples for controllers:
##
## >>> db.mytable.insert(myfield='value')
## >>> rows=db(db.mytable.myfield=='value').select(db.mytable.ALL)
## >>> for row in rows: print row.id, row.myfield
#########################################################################

## after defining tables, uncomment below to enable auditing
# auth.enable_record_versioning(db)

#####################
# Admin settings
admin_emails = ['luca.de.alfaro@gmail.com', 'mshavlov@ucsc.edu', 'mshavlovsky@gmail.com']
# These are the people that can create submission venues.
creator_emails = admin_emails

def is_user_admin():
    return get_user_email() in admin_emails

######################
# Logging
import logging, logging.handlers

class GAEHandler(logging.Handler):
    """
    Logging handler for GAE DataStore
    """
    def emit(self, record):

        from google.appengine.ext import db

        class Log(db.Model):
            name = db.StringProperty()
            level = db.StringProperty()
            module = db.StringProperty()
            func_name = db.StringProperty()
            line_no = db.IntegerProperty()
            thread = db.IntegerProperty()
            thread_name = db.StringProperty()
            process = db.IntegerProperty()
            message = db.StringProperty(multiline=True)
            args = db.StringProperty(multiline=True)
            date = db.DateTimeProperty(auto_now_add=True)

        log = Log()
        log.name = record.name
        log.level = record.levelname
        log.module = record.module
        log.func_name = record.funcName
        log.line_no = record.lineno
        log.thread = record.thread
        log.thread_name = record.threadName
        log.process = record.process
        log.message = record.msg
        log.args = str(record.args)
        log.put()

def get_configured_logger(name):
    logger = logging.getLogger(name)
    if (len(logger.handlers) == 0):
        # This logger has no handlers, so we can assume it hasn't yet been configured
        # (Configure logger)

        # Create default handler
        if request.env.web2py_runtime_gae:
            # Create GAEHandler
            handler = GAEHandler()
            handler.setLevel(logging.WARNING)
            logger.addHandler(handler)
            logger.setLevel(logging.WARNING)
        else:
            # Create RotatingFileHandler
            import os
            formatter="%(asctime)s %(levelname)s %(process)s %(thread)s %(funcName)s():%(lineno)d %(message)s"
            handler = logging.handlers.RotatingFileHandler(os.path.join(request.folder,'private/app.log'),maxBytes=1024,backupCount=2)
            handler.setFormatter(logging.Formatter(formatter))
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)

        # Test entry:
        # logger.debug(name + ' logger created')
    else:
        pass
        # Test entry:
        # logger.debug(name + ' already exists')

    return logger

# Assign application logger to a global var  
logger = get_configured_logger(request.application)

from gluon import current
current.db = db
current.logger = logger
current.is_user_admin = is_user_admin

# Logs timings of db requests.
def log_db(action):
    d = action()
    logger.info(repr(db._timings))
    logger.info("User: %r" % get_user_email())
    return d

response._caller = log_db

# Parameters for job queues.
REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS = 'n_iterations'
REPUTATION_SYSTEM_PARAM_VENUE_ID = 'venue_id'
REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE = 'review_percentage'
REPUTATION_SYSTEM_STARTOVER = 'startover'
REPUTATION_SYSTEM_ALGO = 'algo'
REPUTATION_SYSTEM_RUN_ID = 'run_id'
REPUTATION_SYSTEM_PUBLISH = 'publish'
REPUTATION_SYSTEM_COST_TYPE = 'cost_type'
REPUTATION_SYSTEM_POS_SLOPE = 'pos_slope'
REPUTATION_SYSTEM_NEG_SLOPE = 'neg_slope'
REPUTATION_SYSTEM_NORMALIZE_GRADES = 'normalize_grades'
REPUTATION_SYSTEM_NORMALIZATION_SCALE = 'normalization_scale'
REPUTATION_SYSTEM_NORMALIZE_EACH_ITER = 'normalize_each_iteration'
REPUTATION_SYSTEM_USE_SUBMISSION_RANK_IN_REP = 'use_rank_in_rep'
REPUTATION_SYSTEM_SUBMISSION_RANK_REP_EXP = 'rank_rep_exp'

# Makes the above available to modules.
current.REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS = REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS
current.REPUTATION_SYSTEM_PARAM_VENUE_ID = REPUTATION_SYSTEM_PARAM_VENUE_ID
current.REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE = REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE
current.REPUTATION_SYSTEM_STARTOVER = REPUTATION_SYSTEM_STARTOVER
current.REPUTATION_SYSTEM_ALGO = REPUTATION_SYSTEM_ALGO
current.REPUTATION_SYSTEM_RUN_ID = REPUTATION_SYSTEM_RUN_ID
current.REPUTATION_SYSTEM_PUBLISH = REPUTATION_SYSTEM_PUBLISH
current.REPUTATION_SYSTEM_COST_TYPE = REPUTATION_SYSTEM_COST_TYPE
current.REPUTATION_SYSTEM_POS_SLOPE = REPUTATION_SYSTEM_POS_SLOPE
current.REPUTATION_SYSTEM_NEG_SLOPE = REPUTATION_SYSTEM_NEG_SLOPE
current.REPUTATION_SYSTEM_NORMALIZE_GRADES = REPUTATION_SYSTEM_NORMALIZE_GRADES
current.REPUTATION_SYSTEM_NORMALIZATION_SCALE = REPUTATION_SYSTEM_NORMALIZATION_SCALE
current.REPUTATION_SYSTEM_NORMALIZE_EACH_ITER = REPUTATION_SYSTEM_NORMALIZE_EACH_ITER
current.REPUTATION_SYSTEM_USE_SUBMISSION_RANK_IN_REP = REPUTATION_SYSTEM_USE_SUBMISSION_RANK_IN_REP
current.REPUTATION_SYSTEM_SUBMISSION_RANK_REP_EXP = REPUTATION_SYSTEM_SUBMISSION_RANK_REP_EXP

# Algorithm names
ALGO_OPT = 'opt'
ALGO_DISTR = 'distr'
ALGO_DISTR_NOREP = 'distr'
ALGO_LIST = [ALGO_OPT, ALGO_DISTR]

# Algo defaults
ALGO_DEFAULT_COST_TYPE = 'linear'
ALGO_DEFAULT_POS_SLOPE = 1.0
ALGO_DEFAULT_NEG_SLOPE = 4.0
ALGO_DEFAULT_NUM_ITERATIONS = 10
ALGO_DEFAULT_NORMALIZE = False
ALGO_DEFAULT_NORMALIZATION_SCALE = 1.0
ALGO_DEFAULT_NORMALIZE_EACH_ITER = True
ALGO_DEFAULT_REVIEWS_AS_PERCENTAGE = 25.0
current.ALGO_DEFAULT_REVIEWS_AS_PERCENTAGE = ALGO_DEFAULT_REVIEWS_AS_PERCENTAGE
ALGO_DEFAULT_USE_RANK_IN_REPUTATION = True
ALGO_DEFAULT_RANK_REP_EXP = 0.7

# Settings for email
EMAIL_FROM = "Insert your name"
EMAIL_TO = "info@example.com"
ADMIN_EMAIL_TO = 'admin@example.com'

# These domains and emails can create assignments at will.
IS_VENUE_CREATION_OPEN = True
PREAPPROVED_DOMAINS = []
PREAPPROVED_EMAILS = []
