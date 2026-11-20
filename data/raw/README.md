# Source CSV

The download bundle includes `superstore.csv`, the exact CSV bytes extracted from the user's uploaded `Sample - Superstore.csv.zip`. It is Windows-1252 encoded. The pipeline reads every original cell as text before performing typed transformations.

Source: [Superstore Dataset on Kaggle](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final).

The CSV is ignored by Git. After cloning the code repository, download the source dataset and place its CSV here as `superstore.csv`, or configure `CSV_PATH` in `.env`. The pipeline processes the local Kaggle file; it does not contact Kaggle or download a fresh version on every run.

See `reference_outputs/source_manifest.json` for the original snapshot's SHA-256 and record count. Reference metrics refer to that exact snapshot.
