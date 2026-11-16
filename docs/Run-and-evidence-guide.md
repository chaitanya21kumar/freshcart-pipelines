# Run and evidence guide

Chaitanya Kumar, 23BCS064, CS-8037. Prepared for review on 16 November 2026. Nothing has been uploaded or turned in to Classroom. The repository remains private until the student approves instructor access or publication.

## Run locally

Use Python 3.12 in an isolated environment:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
mage run iris_project iris_classifier --test
python iris_project/run_experiments.py
```

The final local suite passed nine tests. The five real Mage CLI experiments remove old output files before every run; depth 1 fails the 0.8 accuracy gate and produces no prediction or metrics CSV, while depths 2–5 pass. `Iris_Pipeline.ipynb` retains the actual executed Colab experiment outputs. Its optional preview cell has cleared output because it generates an ephemeral password; no real password is committed. The authenticated Cloudflare-hosted Mage graph was captured in `evidence/C3-cloudflare-mage-graph.jpg`. The temporary server and tunnel were stopped after capture. The preview cell was revised for safe reproduction after the working session; core model outputs are unchanged.

## Snowflake

Use your own account. Set the non-secret `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` environment variables. The default native connector asks for an existing password through hidden input; do not put it in a notebook, environment file committed to Git, screenshot or command argument.

```sh
python -m elt.run_experiments
```

Use an isolated fresh FRESHCART database. The runner refuses an already populated bronze table; it does not silently drop it. A deliberate future-order check temporarily inserts a uniquely named synthetic order, then removes that experimental record from bronze and gold to restore the lab. B1–B5 were really executed in the student's trial; `evidence/B-execution.txt` and the B JSON files retain the results. `elt/FreshCart_Experiments.ipynb` displays the exact saved records in review mode and exposes the complete implementation. Its rendered screenshot captions explicitly distinguish recorded real output from live Snowsight. Baseline, history-change and post-bonus gold totals are different snapshots, not contradictory results.

## RabbitMQ and bonus

The actual experiment used the official `rabbitmq:4-alpine` image, listening only on loopback:

```sh
docker run -d --name freshcart-assignment-rabbitmq -p 127.0.0.1:5672:5672 rabbitmq:4-alpine
python -m stream.run_experiment
```

If the saved container already exists, use `docker start freshcart-assignment-rabbitmq` instead. Wait for the broker to become ready. `RABBITMQ_URL` is optional; the local default is used when absent. Never commit a hosted broker URL containing a password.

For the bonus, start the consumer and publish from a second terminal during its one-minute collection window:

```sh
python -m stream.lakehouse_consumer
python -m stream.publish_freshcart
```

The recorded bonus collected two orders in 60.013 seconds, loaded and transformed them, then actually replayed the same payload as a new file. Gold remained 6 orders, INR 9,117.00 and 182 points, with zero changed publication timestamps. These fixed synthetic IDs are a replay demonstration; they are not new distinct business orders on each rerun. The queue acknowledges after closing the raw file, so SQL can be retried from that file. Do not infer exactly-once delivery for every crash scenario.

Stop the broker with `docker stop freshcart-assignment-rabbitmq`. The assignment container and local/Colab preview services were stopped after evidence capture; the Snowflake warehouse was suspended after the actual runs. Generated model/CSV files and private local configuration are ignored by Git.

## Evidence and integrity

`evidence/` contains pre-run prediction files, raw logs, structured actual results and screenshots. The intentional red CI run is 43851429709 (commit 69e3976); the fix is 77fdd83 and green run 43851774140. Later passing runs validate the final dependency/action configuration. See the eight-page report for numbered answers and its separate screenshot appendix. AI assistance was used for implementation, debugging and report preparation. The student must understand the work, check course rules and review the explanations before submission and viva.
