FROM toke/mosquitto:latest
RUN apt-get update
RUN apt-get install -y curl
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get install -y nodejs git make g++ gcc
RUN git clone https://github.com/Koenkk/zigbee2mqtt.git /opt/zigbee2mqtt
WORKDIR /opt/zigbee2mqtt
RUN npm ci
CMD ["npm", "start"]