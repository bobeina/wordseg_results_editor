FROM python:3.5

EXPOSE 9999

RUN apt-get update && apt-get install -y pymongo

# based on python:3.5-onbuild, but if we use that image directly
# the above apt-get line runs too late.
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install -r requirements.txt

COPY . /usr/src/app

CMD python main.py
