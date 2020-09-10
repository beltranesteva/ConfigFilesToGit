FROM python:3-alpine
WORKDIR /usr/src/app
RUN apk --no-cache add ca-certificates
RUN apk add --update \
	python3

COPY . .
RUN pip3 install --no-cache-dir -r requirements.txt
CMD ["python3", "config_to_git.py"]