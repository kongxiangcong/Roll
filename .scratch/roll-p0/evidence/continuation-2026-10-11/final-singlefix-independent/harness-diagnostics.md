# Preservation verifier harness lineage

Behavior batch: 5 PASS /31.09s, no behavior failures.

Append-preservation copied and verified396 files using extended Windows paths. The separate first final verifier omitted that prefix and raised FileNotFoundError on a saved long `.../research-inputs/method-execution/03c842aa959c961bf64bd7cbc08a03482f6898932916526a04e1607db7f4559c.parquet` path. This is verifier path handling, not evidence loss or source mismatch. Only final verifier was corrected to the same extended-path byte reader; no original/source/saved bytes were rewritten, no DB opened, and behavior tests were not repeated.
