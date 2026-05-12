import logging
import traceback

from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, Response

main = Blueprint('main', __name__)

logging.basicConfig(level=logging.INFO)

@main.route('/')
def index():
    return render_template('index.html')