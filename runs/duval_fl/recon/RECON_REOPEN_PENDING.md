# Recon Reopen Pending — Duval County, FL (duval_fl)

Filed 2026-05-21. Framework v5.3.1.

## Status

A **wide Phase 0 re-recon is scheduled for Duval County, post-v5.4.0.** It is
not run now: county builds do not resume until the v5.4.0 pipeline engine ships
(Duval is parked at ESC-002 — the v5.3.0 §16–§20 pipeline architecture is not
implemented in shipped code).

## Re-recon input

The re-recon will use `operator_source_dossier_2026-05-21.md` as its input — a
wide manual recon dossier of **43 candidate sources** the operator compiled for
Duval County / Jacksonville: judicial foreclosure auctions, tax deed auctions,
the tax certificate sale, clerk/court records, property/parcel research, public
notice portals, code/permit/municipal-lien portals, surplus sources, and
third-party aggregators.

## Why the original Phase 0 recon is superseded

The original Phase 0 recon (2026-05-19, `source_of_record_matrix.json` and the
`runs/duval_fl/recon/` artifact set) identified 10 sources and produced a
27-lead-type Source-of-Record Matrix. From that recon, Build Mode carried only
**two sources into built adapters**:

  - `gis_parcels` — JaxGIS ArcGIS parcel layer (Phase 2 — ENRICHMENT only).
  - `clerk_official_records` — or.duvalclerk.com Official Records (Phase 3 —
    PRIMARY event source).

The operator's 43-entry dossier is materially wider than both the original
recon and what was built. It is therefore treated as superseding recon input:
the original Phase 0 matrix will be **rebuilt from scratch** at re-recon time,
not patched.

## What the re-recon must do (post-v5.4.0)

For every source in the dossier:

1. **Empirically probe** the live source — reachability, access pattern,
   portal/vendor fingerprint, document-type taxonomy — exactly as the §01
   County Recon Protocol requires. The dossier is UNVERIFIED operator input;
   nothing in it is framework-verified.
2. **Classify** each source `PRIMARY_EVENT_SOURCE` / `SUPPORTING_EVENT_SOURCE` /
   `ENRICHMENT_SOURCE` / `REFERENCE_SOURCE` / `BLOCKED_SOURCE` per the §13 Lead
   Origination Contract. The dossier's own "use for" notes are operator framing,
   not §13 classification — e.g. third-party aggregators (entries 36–43) are
   almost certainly `REJECTED_SOURCE` (reseller layers, not the record
   authority), and parcel/GIS/tax-roll sources are `ENRICHMENT` regardless of
   how the dossier describes their lead value.
3. **Rebuild the §16 Source-of-Record Matrix** for Duval from the verified set,
   walking the full 27-lead-type sweep.
4. Re-derive the Build Eligibility verdict and re-issue the county config.

## Hard constraints until the re-recon runs

- The dossier is NOT written into `config/counties/duval_fl.json`.
- The §16 Source-of-Record Matrix is NOT rebuilt now.
- The existing built adapters (`gis_parcels`, `clerk_official_records`) are NOT
  reclassified now.
- No adapter is built from the dossier.

The dossier is unverified input until the post-v5.4.0 wide Phase 0 re-recon.

## Trigger

Re-recon is triggered when: (a) the v5.4.0 pipeline engine ships and ESC-002 is
resolved, AND (b) Duval is un-parked for build resumption. Until then this file
stands as the scheduled-work marker.
