# arXiv submission UI

ARG BASE_VERSION=latest

FROM arxiv/base:${BASE_VERSION}

WORKDIR /opt/arxiv/

COPY Pipfile Pipfile.lock /opt/arxiv/
RUN pipenv install && rm -rf ~/.cache/pip

ENV PATH "/opt/arxiv:${PATH}"

COPY wsgi.py uwsgi.ini app.py bootstrap.py /opt/arxiv/
COPY submit/ /opt/arxiv/submit/

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
