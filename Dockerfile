# arXiv submission UI

FROM arxiv/base:latest

WORKDIR /opt/arxiv/

RUN yum install -y which mariadb-devel sqlite
ADD Pipfile Pipfile.lock /opt/arxiv/
RUN pip install -U pip pipenv
ENV LC_ALL en_US.utf-8
ENV LANG en_US.utf-8

RUN pipenv install

ENV PATH "/opt/arxiv:${PATH}"

ADD wsgi.py uwsgi.ini app.py bootstrap.py /opt/arxiv/
ADD submit/ /opt/arxiv/submit/

ENV APPLICATION_ROOT "/"

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
