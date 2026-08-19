# STEG Invoice OCR Expansion — Final Detailed Specification

## 1. Objective

Extend the existing STEG invoice OCR system to extract additional structured information from the invoice calculation table while preserving all currently working functionality.

The OCR system currently extracts invoice-level information such as:

- Consommateur
- Facture
- Date / Mois
- Adresse
- Total 3
- NET À PAYER
- Montant TTC
- Montant HT
- Devise
- Extraction status

The new implementation must add detailed tariff-period information and additional summary amounts.

The existing OCR pipeline, PDF conversion, preprocessing, corrected `Total 3` extraction, corrected `NET À PAYER` extraction, and existing API behavior must not be unnecessarily rewritten or broken.

This is an additive extension.

---

# 2. New fields to extract

The system must extract the following information from the STEG calculation table:

### Detailed tariff information

1. Consommation détaillée
2. Prix Unitaire (P.U.) détaillé
3. Montant détaillé

For each of the four possible tariff periods:

- Jour
- Pointe
- Soirée / Soir
- Nuit

### Summary rows

4. Sous Total
5. Total 1
6. Total 2
7. Total 3
8. NET À PAYER

---

# 3. Canonical data structure

The preferred OCR output structure is:

```json
{
    "consommation_detaillee": {
        "jour": 0,
        "pointe": 0,
        "soiree": 0,
        "nuit": 0
    },

    "prix_unitaire": {
        "jour": 0,
        "pointe": 0,
        "soiree": 0,
        "nuit": 0
    },

    "montant_detaille": {
        "jour": "0.000",
        "pointe": "0.000",
        "soiree": "0.000",
        "nuit": "0.000"
    },

    "sous_total": "0.000",
    "total_1": "0.000",
    "total_2": "0.000",
    "total_3": "0.000",
    "net_a_payer": "0.000"
}
```

Field names should follow this exact convention unless the existing API uses another established naming convention that must remain for compatibility.

---

# 4. Consommation détaillée

Extract the consumption value for each possible tariff period independently.

Required fields:

```text
consommation_detaillee.jour
consommation_detaillee.pointe
consommation_detaillee.soiree
consommation_detaillee.nuit
```

Expected type:

```text
INTEGER
```

Examples:

```text
Jour      → 138025
Pointe    → 39230
Soirée    → 0
Nuit      → 158050
```

## Missing period rule

If a tariff period does not exist in the invoice:

```text
value = 0
```

Do not return:

```text
"Not Found"
null
missing field
```

for these four detailed consumption fields.

Most importantly, the absence of one period must NOT cause subsequent rows to shift.

Example:

```text
Invoice rows:

Jour
Pointe
Nuit
```

must map to:

```json
{
    "jour": value,
    "pointe": value,
    "soiree": 0,
    "nuit": value
}
```

It must NOT map the Nuit value into Soirée.

The row identity must therefore be determined by the row label and spatial position, not by the ordinal position of OCR results.

---

# 5. Prix Unitaire détaillé

Extract the P.U. independently for each tariff period.

Required fields:

```text
prix_unitaire.jour
prix_unitaire.pointe
prix_unitaire.soiree
prix_unitaire.nuit
```

Expected type:

```text
DECIMAL
```

The precision should be compatible with the existing STEG invoices and database schema.

Example:

```text
Jour      → 290
Pointe    → 377
Soirée    → 0
Nuit      → 222
```

## Important

P.U. must be extracted from the **P.U. column**, not inferred from the Montant column.

Do not calculate P.U. unless explicitly needed for validation.

The OCR extractor must associate the P.U. with the correct tariff row.

---

# 6. Detailed Montant

The detailed Montant corresponds to the monetary value associated with each tariff period.

Required fields:

```text
montant_detaille.jour
montant_detaille.pointe
montant_detaille.soiree
montant_detaille.nuit
```

Expected type:

```text
DECIMAL(15,3)
```

Examples:

```text
Jour      → 40027.250
Pointe    → 14789.710
Soirée    → 0.000
Nuit      → 35087.100
```

French invoice formatting must be normalized:

```text
40 027,250 → 40027.250
14 789,710 → 14789.710
35 087,100 → 35087.100
```

Do not lose trailing monetary decimals.

---

# 7. Relationship between Consommation, P.U. and Montant

For validation purposes, the system should verify:

```text
Montant ≈ Consommation × P.U. / 1000
```

Example:

```text
138025 × 290 / 1000 = 40027.250
```

```text
39230 × 377 / 1000 = 14789.710
```

```text
158050 × 222 / 1000 = 35087.100
```

This validation should be used as a consistency check, not as the primary extraction method.

Do not replace an OCR value solely because the calculated value differs unless the implementation explicitly determines the OCR result is unreliable.

Use an appropriate tolerance.

For a missing tariff period:

```text
Consommation = 0
P.U. = 0
Montant = 0.000
```

is valid.

---

# 8. Sous Total

Add:

```text
sous_total
```

The value must be extracted from the explicit `Sous Total` row.

Do not simply select the next monetary value after an OCR label.

The invoice table is spatially structured, and values should be associated with the correct row.

The system should also validate:

```text
sum(montant_detaille)
≈ sous_total
```

Example:

```text
40027.250
+14789.710
+0.000
+35087.100
=89904.060
```

Therefore:

```text
Sous Total = 89904.060
```

The calculated sum is a validation mechanism. The OCR should still attempt to read the actual `Sous Total` row.

---

# 9. Total 1

Add:

```text
total_1
```

Extract the amount from the specific row labeled:

```text
Total 1
```

Do not infer it solely from the rows above it.

Expected type:

```text
DECIMAL(15,3)
```

Example:

```text
Total 1 = 87206.939
```

---

# 10. Total 2

Add:

```text
total_2
```

Extract the amount from the specific row labeled:

```text
Total 2
```

Expected type:

```text
DECIMAL(15,3)
```

Example:

```text
Total 2 = 4598.000
```

---

# 11. Total 3

The current corrected `Total 3` extraction must be preserved.

The old generic strategy:

```text
find label
→ read words to the right
→ take first number
```

must NOT become the primary extraction strategy again.

`Total 3` is a monetary value located in the invoice calculation table. Extraction should be based on the actual row/cell geometry.

The new canonical field is:

```text
total_3
```

For backward compatibility, the existing API field:

```text
total_3(taxes)
```

may remain available and should map to the same value.

Example from the second supplied invoice:

```text
Total 3 = 20799.488
```

---

# 12. NET À PAYER

The current corrected `NET À PAYER` extraction must also be preserved.

The system should continue to use the two available representations when present:

1. Main calculation table
2. Coupon / payment section

The values should be independently OCR'd and compared.

## Validation logic

### Both values exist and agree

Use the value and mark the cross-check as successful.

### Only one value exists

Use the readable value and indicate that independent cross-checking was unavailable.

### Both exist but disagree

Do not silently overwrite one with the other.

Keep both readings internally and mark the extraction for review.

The canonical field is:

```text
net_a_payer
```

The existing API field:

```text
montant ttc
```

should continue to map to the same value where that is the current application's convention.

Example:

```text
NET À PAYER = 113147.577
```

---

# 13. OCR extraction architecture

The calculation table must be treated as a spatial grid.

Do not flatten the entire table into one OCR text string and attempt to reconstruct the fields from OCR order.

The preferred architecture is:

```text
PDF / Image
    ↓
Existing preprocessing pipeline
    ↓
Calculation-table crop
    ↓
image_to_data()
    ↓
Words + coordinates + confidence
    ↓
Detect tariff rows
    ↓
Detect numeric columns
    ↓
Associate values by row + column
    ↓
Normalize numeric formatting
    ↓
Validation
    ↓
Structured result
```

The extractor should use OCR coordinates:

```text
left
top
width
height
line
block
confidence
```

to determine relationships between values and labels.

---

# 14. Calculation-table row model

The extractor should conceptually identify rows such as:

```text
Jour
Pointe
Soirée
Nuit
Sous Total
Bonification
Total 1
Prime de puissance / related charges
Total 2
Taxes
Total 3
NET À PAYER
```

The exact presence of rows can vary between invoice layouts.

Do not assume every invoice has every tariff period.

---

# 15. Column model

The detailed tariff section should be interpreted approximately as:

```text
Montant | P.U. | Consommation | Désignation / Période
```

The exact physical order and coordinates may differ depending on invoice template/resolution, so implementation should rely on calibrated regions and OCR geometry rather than hardcoded assumptions that only work on one image resolution.

The critical requirement is:

```text
same row + correct column
```

for every extracted value.

For example:

```text
Jour
    ├── Consommation → 138025
    ├── P.U.         → 290
    └── Montant      → 40027.250

Pointe
    ├── Consommation → 39230
    ├── P.U.         → 377
    └── Montant      → 14789.710

Soirée
    ├── Consommation → 0
    ├── P.U.         → 0
    └── Montant      → 0.000

Nuit
    ├── Consommation → 158050
    ├── P.U.         → 222
    └── Montant      → 35087.100
```

---

# 16. PDF support

The existing PDF processing must continue to support invoices where the PDF has no text layer.

The pipeline should rasterize the PDF into an image before OCR.

The existing Poppler/pdf2image mechanism should remain supported.

The implementation must ensure that:

- Poppler is correctly located
- PDF conversion works from the backend environment
- the first invoice page is processed when that is the current application behavior
- the OCR receives the rendered image at sufficient resolution

Do not assume that because the PDF opens normally in a browser it contains machine-readable text.

The supplied invoices demonstrate that image-only PDFs are a real use case.

---

# 17. Numeric normalization

All French numeric formats must be normalized consistently.

Examples:

```text
40 027,250 → 40027.250
14 789,710 → 14789.710
89 904,060 → 89904.060
113 147,577 → 113147.577
```

Remove thousands spaces.

Convert comma decimal separators to dots.

Preserve three decimal places for monetary values.

Do not use binary floating-point representation as the database storage type for monetary values.

---

# 18. Database requirements

Add storage for the following:

### Consumption

```text
consumption_jour
consumption_pointe
consumption_soiree
consumption_nuit
```

Recommended type:

```text
INTEGER
```

### P.U.

```text
pu_jour
pu_pointe
pu_soiree
pu_nuit
```

Recommended type:

```text
DECIMAL(12,3)
```

### Detailed Montant

```text
montant_jour
montant_pointe
montant_soiree
montant_nuit
```

Recommended type:

```text
DECIMAL(15,3)
```

### Summary monetary fields

```text
sous_total
total_1
total_2
total_3
net_a_payer
```

Recommended type:

```text
DECIMAL(15,3)
```

Do NOT use FLOAT for these monetary columns.

Use the database's existing naming and migration conventions where applicable.

---

# 19. API/backend requirements

Update all relevant backend layers:

1. Database model
2. Database migration
3. OCR service
4. Invoice processing/upload service
5. API response model/schema
6. Serialization
7. Frontend invoice response handling

The API should expose the new information in structured form.

Recommended response:

```json
{
    "consommation_detaillee": {
        "jour": 138025,
        "pointe": 39230,
        "soiree": 0,
        "nuit": 158050
    },
    "prix_unitaire": {
        "jour": 290,
        "pointe": 377,
        "soiree": 0,
        "nuit": 222
    },
    "montant_detaille": {
        "jour": "40027.250",
        "pointe": "14789.710",
        "soiree": "0.000",
        "nuit": "35087.100"
    },
    "sous_total": "89904.060",
    "total_1": "87206.939",
    "total_2": "4598.000",
    "total_3": "20799.488",
    "net_a_payer": "113147.577"
}
```

---

# 20. Backward compatibility

Do not remove or rename existing fields that are already consumed by the platform.

Existing fields such as:

```text
consomateur
facture
date
address
montant ttc
montant ht
devise
status
```

must continue working.

Existing `Total 3` and `NET À PAYER` fields must continue working.

Where a new canonical field overlaps with an existing field, expose both temporarily if necessary.

Example:

```text
total_3
total_3(taxes)
```

Both should represent the same value.

Likewise:

```text
net_a_payer
montant ttc
```

should remain synchronized where the current platform treats them as equivalent.

---

# 21. Missing-value policy

## Detailed tariff data

For:

```text
consommation_detaillee
prix_unitaire
montant_detaille
```

missing tariff period = zero.

Example:

```json
{
    "jour": 138025,
    "pointe": 39230,
    "soiree": 0,
    "nuit": 158050
}
```

This does NOT mean OCR failed.

It means the invoice did not contain that tariff period.

## Mandatory invoice-level values

For:

```text
sous_total
total_1
total_2
total_3
net_a_payer
```

an OCR failure must NOT automatically become `0`.

Use the application's existing `Not Found`, `null`, or review convention.

A genuine financial value of zero must remain distinguishable from an OCR failure.

---

# 22. Validation and confidence

The system should maintain confidence information for newly extracted values where possible.

At minimum, confidence should consider:

- OCR confidence
- agreement across preprocessing/PSM variants
- row/column positional consistency
- arithmetic consistency

The arithmetic checks are particularly useful:

```text
Consumption × P.U. / 1000 ≈ Montant
```

and:

```text
sum(detailed Montant) ≈ Sous Total
```

A mismatch should not necessarily reject the invoice, but should lower confidence and mark the field for review.

---

# 23. Frontend requirements

Display the detailed tariff information as a table.

Recommended UI:

```text
| Période | Consommation | P.U. | Montant |
|---------|--------------|------|---------|
| Jour    | 138025       | 290  | 40027.250 |
| Pointe  | 39230        | 377  | 14789.710 |
| Soirée  | 0            | 0    | 0.000 |
| Nuit    | 158050       | 222  | 35087.100 |
```

Then display summary values:

```text
Sous Total       89 904.060
Total 1          87 206.939
Total 2           4 598.000
Total 3          20 799.488
NET À PAYER     113 147.577
```

Existing OCR warning/review indicators should remain available.

---

# 24. Required regression test — supplied invoice

The supplied `facture8.pdf` must be used as a mandatory regression test.

Expected values:

```json
{
    "consommation_detaillee": {
        "jour": 138025,
        "pointe": 39230,
        "soiree": 0,
        "nuit": 158050
    },
    "prix_unitaire": {
        "jour": 290,
        "pointe": 377,
        "soiree": 0,
        "nuit": 222
    },
    "montant_detaille": {
        "jour": "40027.250",
        "pointe": "14789.710",
        "soiree": "0.000",
        "nuit": "35087.100"
    },
    "sous_total": "89904.060",
    "total_1": "87206.939",
    "total_2": "4598.000",
    "total_3": "20799.488",
    "net_a_payer": "113147.577"
}
```

These values are a regression-test expectation derived from the supplied invoice example.

They must NOT be hardcoded into the OCR program.

---

# 25. Additional regression requirement

The earlier supplied invoice must remain a regression test for the already corrected extraction of:

```text
Total 3
NET À PAYER
Montant HT
```

The new implementation must not cause these previously corrected fields to regress.

The test suite should therefore include:

1. Previous invoice
2. `facture8.pdf`
3. At least one invoice without a Soirée tariff row
4. At least one invoice with all four tariff periods

---

# 26. Important implementation constraint

Do not build the new extraction around a single OCR pass.

Do not assume:

```text
OCR order = table order
```

Do not assume:

```text
first number = first field
```

Do not assume:

```text
label → value is always to the right
```

The STEG invoice layout requires spatial extraction.

Use:

```text
row detection
+
column detection
+
OCR coordinates
+
targeted numeric OCR
+
validation
```

The previous `Total 3` / `NET À PAYER` issue demonstrated that generic label-to-right extraction can return a valid-looking number from the wrong location.

The new detailed fields must avoid reproducing that failure.

---

# 27. Final acceptance criteria

The implementation is considered complete only when:

- Existing invoice OCR still works.
- PDF uploads still work.
- Existing `Total 3` extraction still works.
- Existing `NET À PAYER` cross-check still works.
- `Consommation` is correctly mapped by tariff period.
- P.U. is correctly mapped by tariff period.
- Detailed Montant is correctly mapped by tariff period.
- Missing tariff periods become zero.
- Missing periods do not shift subsequent rows.
- Sous Total is correctly extracted.
- Total 1 is correctly extracted.
- Total 2 is correctly extracted.
- Total 3 is correctly extracted.
- NET À PAYER is correctly extracted.
- Monetary values are stored as DECIMAL, not FLOAT.
- The database migration succeeds.
- API schemas expose the new fields.
- Frontend displays the new fields.
- The supplied `facture8.pdf` regression test produces the expected values.
- The previous invoice regression test continues to pass.
- No invoice values are hardcoded to the supplied examples.