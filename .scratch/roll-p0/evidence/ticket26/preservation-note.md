# Runtime preservation retry

The first parallel copy stopped on a resolved-target containment assertion. A subsequent read-only scan over every planned target found no containment failure. The exact transient path/cause was not captured; this is an archive-environment failure, not product evidence.

The initial script and copied files are retained. Version2 adds explicit Windows extended paths, normalizes the extended prefix in containment comparisons, and serializes directory resolution/creation. It reuses the existing protected-source receipt without rewriting it, verifies source guards again, and accepts an existing destination only with identical SHA256 and length. Existing differing bytes cause refusal. No runtime, receipt, source or database is cleaned or overwritten. The final manifest is emitted only after every listed file is checked successfully.
