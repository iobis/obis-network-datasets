# obis-network-datasets

This Python package creates issues for datasets linked to the OBIS network in the GBIF registry.

Since the release of IPT 2.5.2, publishers can select the networks their dataset belongs to in IPT. GBIF and OBIS recommend that all marine publishers select OBIS where appropriate. 

Datasets that are added to the OBIS network appear here: https://www.gbif.org/network/2b7c7b4f-4d4f-40d3-94de-c28b6fa054a6 (note that while the dataset appears immediately the occurrence records reprocess so lag behind a little).

The OBIS secretariat will list those marine datasets that are not yet in OBIS as issues to this GitHub repository and indicate which OBIS node(s) should endorse this dataset. Once endorsed, OBIS will harvest the dataset directly from the source IPT and list it on the OBIS node page.

GitHub accounts per OBIS node used to assign datasets:
- AntOBIS: @ymgan
- IndOBIS: @johnny3125
- Caribbean OBIS: @diodon
- OBIS Japan: @hosonot
- EurOBIS: @rubenpp7
- OBIS Australia: @obisau 
- OBIS Deepsea: @haniehsaeedi
- AfrOBIS: @TRasehlomi
- OBIS China: @ZhaocuiMeng

## Run

Create `.env` file with environment variables `GITHUB_USER` and `GITHUB_ACCESS_TOKEN`.

```
python -m obisnd
```
