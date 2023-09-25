from flask import Flask, request, render_template
import os
import random
import redis
import socket
import sys
import logging
from logging import StreamHandler
from datetime import datetime

from opencensus.ext.azure import metrics_exporter
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.flask.flask_middleware import FlaskMiddleware


# Instrumentation Key
INSTRUMENTATION_KEY = '750f1ec9-6008-413d-bac7-bf6bcbb88a5b'

# App Insights
# TODO: Import required libraries for App Insights
from opencensus.ext.azure.log_exporter import AzureEventHandler

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(AzureLogHandler(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'))
# Add StreamHandler
stream_handler = StreamHandler()
logger.addHandler(stream_handler)

# Metrics
exporter = metrics_exporter.new_metrics_exporter(
  enable_standard_metrics=True,
  connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'
)

# Tracing
tracer = Tracer(
    exporter=AzureExporter(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'),
    sampler=ProbabilitySampler(1.0)
)

app = Flask(__name__)

# Requests
middleware = FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'),
    sampler=ProbabilitySampler(rate=1.0)
)

# Load configurations from environment or config file
app.config.from_pyfile('config_file.cfg')

if ("VOTE1VALUE" in os.environ and os.environ['VOTE1VALUE']):
    button1 = os.environ['VOTE1VALUE']
else:
    button1 = app.config['VOTE1VALUE']

if ("VOTE2VALUE" in os.environ and os.environ['VOTE2VALUE']):
    button2 = os.environ['VOTE2VALUE']
else:
    button2 = app.config['VOTE2VALUE']

if ("TITLE" in os.environ and os.environ['TITLE']):
    title = os.environ['TITLE']
else:
    title = app.config['TITLE']

# Redis Connection
r = redis.Redis()

# Redis configurations
#redis_server = os.environ['REDIS']

"""# Redis Connection to another container
try:
   if "REDIS_PWD" in os.environ:
      r = redis.StrictRedis(host=redis_server,
                        port=6379,
                        password=os.environ['REDIS_PWD'])
   else:
      r = redis.Redis(redis_server)
   r.ping()
except redis.ConnectionError:
   exit('Failed to connect to Redis, terminating.')"""



# Change title to host name to demo NLB
if app.config['SHOWHOST'] == "true":
    title = socket.gethostname()

# Init Redis
if not r.get(button1): r.set(button1,0)
if not r.get(button2): r.set(button2,0)

@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'GET':

        # Get current values
        vote1 = r.get(button1).decode('utf-8')
        # TODO: Use tracer object to trace cat vote
        with tracer.span(name='cat_vote_trace') as span:
            span.add_attribute('cat_vote_value', vote1)
            properties = {'custom_dimensions': {'cat_vote_value': vote1}}
            logger.info('Cat vote retrieved', extra=properties)


        vote2 = r.get(button2).decode('utf-8')
        # TODO: use tracer object to trace dog vote
        with tracer.span(name='dog_vote_trace') as span:
            span.add_attribute('dog_vote_value', vote2)
            properties = {'custom_dimensions': {'dog_vote_value': vote2}}
            logger.info('Dog vote retrieved', extra=properties)

        # Return index with values
        return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

    elif request.method == 'POST':

        if request.form['vote'] == 'reset':

            # Empty table and return results
            r.set(button1,0)
            r.set(button2,0)
            vote1 = r.get(button1).decode('utf-8')
            properties = {'custom_dimensions': {'Cats Vote': vote1}}
            # TODO: use logger object to log cat vote
            logger.info('Cat vote reset', extra=properties)

            vote2 = r.get(button2).decode('utf-8')
            properties = {'custom_dimensions': {'Dogs Vote': vote2}}
            # TODO: use logger object to log dog vote
            logger.info('Dog vote reset', extra=properties)

            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

        else:

            # Insert vote result into DB
            vote = request.form['vote']
            r.incr(vote,1)

            # Get current values
            vote1 = r.get(button1).decode('utf-8')
            vote2 = r.get(button2).decode('utf-8')

            with tracer.span(name='cat_vote_trace') as span:
                span.add_attribute('cat_vote_value', vote1)
                properties = {'custom_dimensions': {'cat_vote_value': vote1}}
                logger.info('Cat vote retrieved', extra=properties)

            with tracer.span(name='dog_vote_trace') as span:
                span.add_attribute('dog_vote_value', vote2)
                properties = {'custom_dimensions': {'dog_vote_value': vote2}}
                logger.info('Dog vote retrieved', extra=properties)

            # Return results
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

if __name__ == "__main__":
    # TODO: Use the statement below when running locally
    #app.run() 
    # TODO: Use the statement below before deployment to VMSS
     app.run(host='0.0.0.0', threaded=True, debug=True) # remote
