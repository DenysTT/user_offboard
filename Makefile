APP_NAME = bamboo_user_checker
ifdef GIT_BRANCH
endif

.PHONY: default
default: clean linux

.PHONY: all
all: default deploy clean

.PHONY: linux
linux:
	docker run -v $(PWD):/data -w /data -e GIT_BRANCH=$(GIT_BRANCH) python:3.7.2 make linux-inside

.PHONY: linux-inside
linux-inside:
	pip3 install pipenv
	pipenv sync
	pipenv run pyinstaller --onefile bamboo_api.py -n $(APP_NAME)

.PHONY: clean
clean:
	docker run -v $(PWD):/data -w /data python:3.7.2 make clean-inside

.PHONY: clean-inside
clean-inside:
	rm -fr ./build
	rm -fr ./dist
	rm -fr ./__pycache__
	rm -f *.spec

.PHONY: deploy
deploy:
	scp ./dist/$(APP_NAME) /opt/tools/$(APP_NAME)

