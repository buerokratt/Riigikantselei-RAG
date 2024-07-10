#!/bin/bash

# retrieve version from file
version_file="./VERSION"
version=$(cat "$version_file")

# build latest image
docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/riigikantselei_api:latest -f ./docker/Dockerfile .

#docker tag docker.texta.ee/texta/riigikantselei_api:latest docker.texta.ee/texta/riigikantselei_api:$version
#docker push docker.texta.ee/texta/riigikantselei_api:$version

docker push docker.texta.ee/texta/riigikantselei_api:latest
