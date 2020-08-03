FROM node:6-alpine

# 2: Download+Install PhantomJS, as the npm package 'phantomjs-prebuilt' won't work on alpine!
# See https://github.com/dustinblackman/phantomized
RUN set -ex \
  && apk add --no-cache --virtual .build-deps ca-certificates openssl python-dev py-pip \
  && apk add --no-cache --update python \
  && wget -qO- "https://github.com/dustinblackman/phantomized/releases/download/2.1.1/dockerized-phantomjs.tar.gz" | tar xz -C / \
  && npm install -g phantomjs \
  && pip install selenium

COPY bamboo_api.py .

CMD ["python", "bamboo_api.py"]