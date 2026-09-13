# Model artifact manifests

Model **weights are not committed** — they are distributed through the registry and
fetched by checksum. What lives here are the manifests that make a model version
reproducible and verifiable:

- artifact checksum (so a tampered or truncated download is detected)
- preprocessing hash (band order, scale, normalisation statistics)
- training data reference and split
- the metrics the version was accepted on

Why the manifests are committed and the weights are not: reverting a code commit
does not revert model weights. The registry must be able to pin and roll back a
*model version* independently of the code version, and that is only possible if the
pin is a tracked file.
