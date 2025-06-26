# app.py
import os, logging
from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv


logging.getLogger("pymongo").setLevel(logging.WARNING)
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY','CHANGE_ME')
app.jinja_env.filters['basename'] = lambda value: os.path.basename(value)

# Mail config (for sending to experts)
app.config.update(
    MAIL_SERVER   = os.getenv('MAIL_SERVER', 'localhost'),
    MAIL_PORT     = int(os.getenv('MAIL_PORT', 25)),
    MAIL_USERNAME = os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD'),
    MAIL_USE_TLS  = os.getenv('MAIL_USE_TLS', 'False').lower() in ('1','true','yes')
)

# Mongo
mongo = MongoClient(os.getenv('MONGO_URI'))
# register blueprints
from auth import bp as auth_bp
from doctor import bp as doc_bp
from lab import bp as lab_bp
from radiology import bp as rad_bp
from coordinator import bp as coord_bp

app.register_blueprint(auth_bp)
app.register_blueprint(doc_bp, url_prefix='/doctor')
app.register_blueprint(lab_bp, url_prefix='/lab')
app.register_blueprint(rad_bp, url_prefix='/rad')
app.register_blueprint(coord_bp, url_prefix='/coord')

# Error handlers, static download route, etc. remain here

if __name__=='__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, host='0.0.0.0',port=5000)
