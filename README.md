# From Git to Gold

Data Engineering CS-8037 assignment preparation for Chaitanya Kumar, 23BCS064.

The project combines Git and CI, FreshCart Snowflake ELT, a Mage Iris classification pipeline, RabbitMQ topic routing and a one-minute stream-to-gold bonus consumer.

## Report and submission
[Download the assignment report (PDF)](https://github.com/chaitanya21kumar/freshcart-pipelines/releases/download/assignment-2026-11-16/23BCS064_Chaitanya_Kumar_Pipelines.pdf). It contains eight report body pages and ten screenshot appendix pages. The report and this public repository were submitted through Google Classroom on 16 November 2026; Classroom showed **Turned in**.

The school Drive account was over its storage allowance, so the PDF was attached in Classroom as a direct public download link rather than a Drive upload. Both submission links can be opened without requesting repository access.

The FreshCart sample records and baseline SQL, and the Iris block design, come from the course reference notebooks. Assignment extensions, tests and evidence are recorded here. AI assistance was used in implementation, debugging and report preparation. The student is responsible for understanding the work, following course rules and explaining it in the viva. The release tag pins the implementation and evidence used in the report; this subsequent documentation update records the completed submission.

## Safety
Use only your own Snowflake trial and synthetic lecture data. No instructor login is included. Credentials are read from environment variables or an interactive prompt and must never enter Git. A local RabbitMQ container is bound to loopback only. Generated CSV and model files are intentionally ignored.

## Setup
Python 3.12 is required. Create a virtual environment, install requirements.txt, and run `python -m pytest -q`. The notebooks contain reproducible experiments and record their actual output. See docs for detailed run instructions and evidence status.
