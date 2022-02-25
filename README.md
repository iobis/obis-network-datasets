# obis-network-datasets

This Python package creates issues for datasets linked to the OBIS network in the GBIF registry.

Since the release of IPT 2.5.2, publishers can select the networks their dataset belongs to in the EML metadata. GBIF and OBIS recommends that all marine publishers select OBIS where appropriate. 

Datasets that are added to OBIS appear here: https://www.gbif.org/network/2b7c7b4f-4d4f-40d3-94de-c28b6fa054a6 (note that while the dataset appears immediately the occurrence records reprocess so lag behind a little).

The OBIS secretariat will list those marine datasets that are not yet in OBIS as issues to this GitHub repository and indicate which OBIS node(s) should endorse this dataset. Once endorsed, the OBIS secretariat will harvest the dataset directly from the source IPT and list it on the OBIS node page.

## Run

Create `.env` with environment variables `GITHUB_USER` and `GITHUB_ACCESS_TOKEN`.

```
python -m obisnd
```
