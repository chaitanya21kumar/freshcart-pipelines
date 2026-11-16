# From Git to Gold

Data Engineering CS-8037 assignment preparation for Chaitanya Kumar, 23BCS064.

The project combines Git and CI, FreshCart Snowflake ELT, a Mage Iris classification pipeline, RabbitMQ topic routing and a one-minute stream-to-gold bonus consumer.

## Origin and review
The FreshCart sample records and baseline SQL, and the Iris block design, come from the course reference notebooks. Assignment extensions, tests and evidence are recorded here. This is AI-assisted preparation for student review; the student must understand and verify the work and comply with the course rules before submitting or defending it in the viva. It has not been submitted to Google Classroom.

## Safety
Use only your own Snowflake trial and synthetic lecture data. No instructor login is included. Credentials are read from environment variables or an interactive prompt and must never enter Git. A local RabbitMQ container is bound to loopback only. Generated CSV and model files are intentionally ignored.

## Setup
Python 3.12 is required. Create a virtual environment, install requirements.txt, and run `python -m pytest -q`. The notebooks contain reproducible experiments and record their actual output. See docs for detailed run instructions and evidence status.
