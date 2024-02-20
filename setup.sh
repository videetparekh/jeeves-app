#!bin/bash

read -p "Please enter your DEEPGRAM_API_KEY: " dg_key
read -p "Please enter your OPENAI_API_KEY: " oai_key

# Check if the .env file exists, if not, create it
if [ ! -f app/.env ]; then
    touch app/.env
fi

# Write the API key to the .env file
echo "DEEPGRAM_API_KEY=$dg_key" >> app/.env
echo "OPENAI_API_KEY=$oai_key" >> app/.env

echo "API key has been successfully written to .env file."

docker build -t jeeves_img .
