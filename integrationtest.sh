#!/bin/bash
#export SERVICES='filemanager compiler-api compiler-worker submission-worker submission-agent submission-ui submission-preview legacy-filesystem plaintext-worker plaintext-api mailhog submission-ui-redis  submission-ui-maria   submission-agent-maria   filemanager-maria   mock-classifier   submission-localstack integration-test'
export AWS_ACCESS_KEY_ID=fookey
export AWS_SECRET_ACCESS_KEY=foosecretkey
#export CONVERTER_DOCKER_IMAGE=626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter:0.9
export CONVERTER_DOCKER_IMAGE=626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-2016:0.1.5
export DIND_SOURCE_ROOT=/tmp/subui-quickstart-compiler-dind-src-root
mkdir -p $DIND_SOURCE_ROOT
#docker-compose rm -vf
#docker-compose build
docker-compose -f docker-compose.yml -f docker-compose.intgtest.yml up
