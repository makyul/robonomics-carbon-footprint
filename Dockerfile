FROM python:3.6
RUN pip3 install robonomics-interface pyyaml paho-mqtt 
COPY plug.py plug.py
CMD ["python3", "plug.py"]