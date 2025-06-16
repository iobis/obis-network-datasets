# obis-network-datasets

This Python package creates issues for datasets linked to the OBIS network in the GBIF registry.

Since the release of IPT 2.5.2, publishers can select the networks their dataset belongs to in IPT. GBIF and OBIS recommend that all marine publishers select OBIS where appropriate. 

Datasets that are added to the OBIS network appear here: https://www.gbif.org/network/2b7c7b4f-4d4f-40d3-94de-c28b6fa054a6 (note that while the dataset appears immediately the occurrence records reprocess so lag behind a little).

The OBIS secretariat will list those marine datasets that are not yet in OBIS as issues to this GitHub repository and indicate which OBIS node(s) should endorse this dataset. Once endorsed, OBIS will harvest the dataset directly from the source IPT and list it on the OBIS node page.

GitHub accounts per OBIS node used to assign datasets:
- AntOBIS: @ymgan
- IndOBIS: @johnny3125
- Caribbean OBIS: @diodon, @cperaltab
- OBIS Japan: @hosonot
- EurOBIS: @rubenpp7
- OBIS Australia: @obisau 
- OBIS Deepsea: @haniehsaeedi
- AfrOBIS: @TRasehlomi
- OBIS China: @ZhaocuiMeng
- OBIS Canada: @cornthwaitem
- OBIS Ecuador: @vechocho, @gbif-ec
- OBIS UK: @dblear
- Ocean Tracking Network: @jdpye

To view all issues which are not currently assigned to a node, [use this filter](https://github.com/iobis/obis-network-datasets/issues?q=is%3Aissue%20state%3Aopen%20no%3Aassignee%20label%3Adataset%20-label%3A%22node%3A%20OBIS%20China%22%20-label%3A%22node%3A%20OBIS%20SEAMAP%22%20-label%3A%22node%3A%20OBIS%20Colombia%22%20-label%3A%22node%3A%20OBIS%20Malaysia%22%20-label%3A%22node%3A%20OBIS%20Deep%20Sea%22%20%20-label%3A%22node%3A%20OBIS%20Brazil%22%20-label%3A%22node%3A%20OBIS%20Argentina%22%20-label%3A%22node%3A%20OBIS%20Australia%22%20-label%3A%22node%3A%20ESP%20OBIS%22%20-label%3A%22node%3A%20OBIS%20Black%20Sea%22%20-label%3A%22node%3A%20Caribbean%20OBIS%22%20-label%3A%22node%3A%20AfroOBIS%22%20-label%3A%22node%3A%20EurOBIS%22%20-label%3A%22node%3A%20OBIS%20CPPS%22%20-label%3A%22node%3A%20OBIS%20Ecuador%22%20-label%3A%22node%3A%20OBIS%20Norway%22%20-label%3A%22node%3A%20OBIS%20UK%22%20-label%3A%22node%3A%20OBIS%20USA%22%20-label%3A%22node%3A%20SWP%20OBIS%22).

## Run

Create `.env` file with environment variables `GITHUB_USER` and `GITHUB_ACCESS_TOKEN`.

```
python -m obisnd
```
