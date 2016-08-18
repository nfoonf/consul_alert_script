FROM python:3.3-alpine

COPY requirements.txt /usr/src/app/
RUN pip  install -v -r   /usr/src/app/requirements.txt
# RUN pip --cert cacert.pem install -r -v  requirements.txt
ADD alerter.py .
CMD [ "python3", "-u", "./alerter.py" ] 
