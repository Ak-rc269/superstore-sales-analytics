# Reference outputs

These files were computed locally from the uploaded CSV using the same pure transformation function that the pipeline uses. They provide known values for checking the first real database run and the Dashboard.

They do not record a PostgreSQL run, Google Sheets upload or completed Data Studio report. After the pipeline runs on your computer, it writes fresh CSVs and `data_quality.json` into `outputs/`.

- The five summary CSVs correspond to the five planned analysis questions.
- `data_quality.json` records checks and cleaning counts from the supplied snapshot.
- `source_manifest.json` identifies the source bytes and calculation environment.

All monetary columns retain the source file's units. The CSV has no currency-code column. Ratios are stored as fractions; format a `profit_margin` value as a percentage to display it.
