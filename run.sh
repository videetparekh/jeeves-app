#!bin/bash

docker stop jeeves
docker rm jeeves

docker run -it -v $PWD/artifacts:/app/artifacts/ --device /dev/null:/dev/snd -v $PWD/app:/app -p 8501:8501 --name jeeves jeeves_img
