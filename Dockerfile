# arXiv submission UI

ARG BASE_VERSION=0.16.6

FROM arxiv/base:${BASE_VERSION}

WORKDIR /opt/arxiv/

ENV PIPENV_VENV_IN_PROJECT 1

COPY Pipfile Pipfile.lock /opt/arxiv/
#RUN pipenv sync && rm -rf ~/.cache/pip
RUN pipenv install --skip-lock && rm -rf ~/.cache/pip

ENV PATH "/opt/arxiv:${PATH}"

COPY wsgi.py uwsgi.ini app.py bootstrap.py /opt/arxiv/
COPY submit/ /opt/arxiv/submit/

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
