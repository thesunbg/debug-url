FROM mcr.microsoft.com/playwright
USER root
RUN apt update
RUN apt install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get install -y python3.9
RUN apt-get install -y pip
RUN pip install --upgrade pip

# install playwrite
RUN pip install flask
RUN pip install playwright
RUN playwright install
RUN playwright install-deps
RUN pip install python-Wappalyzer
RUN pip install playwright-stealth
RUN apt-get install -y dbus
#USER seluser
WORKDIR /srv
COPY . /srv
ENV FLASK_APP=app
CMD ["flask","--app", "main", "run", "--host", "0.0.0.0", "--port", "6000"]