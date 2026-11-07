# Data pipeline report · run 20261107-211726

## Luxembourg apartment asking prices roughly doubled from 2010 to a 2022 peak, then eased; the data is usable once 620 suppressed price rows are treated as missing.

### Key findings
- Median asking price per commune rose from €328,999 in 2010 to a peak of €829,814 in 2022, then eased to €713,460 in 2025.
- Median price per m² went from €3,619 in 2010 to a peak of €8,470 in 2022, dipped to €7,427 in 2024 and was €7,661 in 2025. The steepest rise came in 2019–2021 (€5,176 in 2018 to €7,903 in 2021).
- In 2025 Luxembourg was the most expensive commune at €12,362 per m², followed by Bertrange (€11,331) and Strassen (€10,780). Wiltz was the cheapest at €5,628 per m².
- Among the 54 communes with prices in both 2010 and 2025, the median commune's price per m² rose 106.4%. Bertrange grew fastest (+163.1%) and Echternach slowest (+79.3%).
- All 12 validation rules passed, with no duplicate commune-year pairs and no missing keys, across 1,675 rows.

### Data caveats
- 620 of 1,675 rows (about 37%) have prices suppressed with '*'. These are probably small, rural communes, so national figures may lean towards larger, pricier markets.
- The number of communes changes from year to year: 116 in 2010 falling to 100 in 2023–2025. Only 50 to 94 communes have published prices in a given year, so part of the yearly movement may reflect which communes are included.
- These are asking prices, not sale prices. They are unweighted averages per commune, so they describe the typical commune, not the typical apartment.
- 32 rows have zero listings, and their prices should be treated as missing.
- The data covers 1,675 rows rather than the 2,048 possible commune-years. The check for commune-name spelling variants has not been run yet.

### Next steps
- Convert '*' to NULL in both price columns, add a suppressed flag, and cast year and n_listings to integers on load.
- Ask the data owner what '*' means and why 1,675 rows exist instead of 2,048. Cross-tabulate suppressed rows against n_listings to confirm the suppression rule.
- For trend analysis, build a panel of communes present in every year, or report the commune count alongside each yearly figure.
- Run a similar-spelling check on the 128 commune names before joining to other data.
- Confirm whether prices are nominal or inflation-adjusted, and identify the data source and collection method.

### Summary (en)

Apartment asking prices in Luxembourg's communes rose sharply between 2010 and 2022 and have eased since. The median price per square metre went from €3,619 in 2010 to a peak of €8,470 in 2022, with the fastest gains in 2019–2021. It was €7,661 in 2025. Among the 54 communes with data in both 2010 and 2025, the median commune's price rose 106.4%, and even the slowest grew by about 80%. Luxembourg city (€12,362/m²) and Bertrange lead the market, while northern rural communes such as Wiltz (€5,628/m²) are the cheapest. The dataset passed all 12 integrity checks. However, 620 of 1,675 rows have suppressed prices, and the set of communes shifts from year to year. National figures should therefore be read with care, and they reflect asking prices, not sale prices.

### Summary (fr)

Les prix demandés pour les appartements au Luxembourg ont nettement progressé entre 2010 et 2022, avant de se replier légèrement. Le prix médian au mètre carré, de 3 619 € en 2010, a atteint un sommet de 8 470 € en 2022 et s'établissait à 7 661 € en 2025. La hausse la plus vive s'est concentrée sur 2019-2021. Sur les 54 communes renseignées en 2010 comme en 2025, la commune médiane a vu son prix grimper de 106,4 %, et même les moins dynamiques ont progressé d'environ 80 %. La capitale (12 362 €/m²) et Bertrange dominent le marché, tandis que les communes rurales du nord, comme Wiltz (5 628 €/m²), restent les plus abordables. Les 12 contrôles d'intégrité sont tous validés. Toutefois, 620 des 1 675 lignes ont un prix masqué et la liste des communes varie d'une année à l'autre. Il convient donc d'interpréter les chiffres nationaux avec prudence, d'autant qu'il s'agit de prix demandés et non de prix de vente.

### Summary (ar)

شهدت أسعار الشقق المعروضة في بلديات لوكسمبورغ ارتفاعاً حاداً بين عامي 2010 و2022، ثم تراجعت قليلاً بعد ذلك. فقد ارتفع متوسط السعر الوسيط للمتر المربع من 3,619 يورو في 2010 إلى ذروة بلغت 8,470 يورو في 2022، وكانت أسرع الزيادات خلال الفترة 2019-2021، ليستقر عند 7,661 يورو في 2025. وفي البلديات الـ54 التي تتوفر بياناتها في عامَي 2010 و2025، ارتفع سعر البلدية الوسيطة بنسبة 106.4%، بل إن أبطأها نمواً سجّل زيادة تقارب 80%. وتتصدر مدينة لوكسمبورغ (12,362 يورو للمتر المربع) وبيرترانج قائمة الأغلى، في حين تبقى البلديات الريفية في الشمال، مثل فيلتز (5,628 يورو)، الأقل كلفة. وقد اجتازت البيانات جميع فحوص السلامة الاثني عشر، غير أن 620 صفاً من أصل 1,675 أسعارها محجوبة، كما تتغير قائمة البلديات من سنة إلى أخرى. لذا ينبغي قراءة الأرقام الوطنية بحذر، مع التذكير بأنها أسعار معروضة وليست أسعار بيع فعلية.

## Data quality issues

| Severity | Column | Issue | Real problem? | Fix |
|---|---|---|---|---|
| high | avg_price_eur | Non-numeric placeholder (asterisk) used in place of averages, likely for suppressed small samples. | yes | Convert the asterisk placeholder to a true missing value (NULL) before casting to decimal, and never average it as text. Keep a separate flag column such as suppressed=1 so analysts can tell suppression apart from genuinely absent data. |
| high | avg_price_per_m2_eur | Same asterisk placeholder as avg_price_eur, appearing in the same rows. | yes | Map the asterisk to NULL and cast to decimal. Derive the suppression flag from the same condition as avg_price_eur and check that both columns are suppressed in the same rows. |
| medium | n_listings | Zero counts exist, so average prices for those rows may be undefined or meaningless. | yes | Check whether the 32 zero-count rows carry numeric prices or asterisks. Set prices to NULL where n_listings is 0, and confirm zero means no listings rather than a data-collection gap. |
| medium | avg_price_eur | Suppression may not be tied to small n_listings, which the column note assumes; this is unverified. | yes | Cross-tabulate asterisk rows against n_listings (for example, the share suppressed below a threshold) to confirm the suppression rule before documenting the placeholder meaning. |
| low | n_listings | IQR outliers on the high side, consistent with a few large communes. | no | Keep these rows. Note that the IQR rule flags about 10% of rows because of the skewed distribution, and avoid removing them. Use medians or log scales where scale matters. |
| low | avg_price_eur | IQR outliers that appear to be genuinely expensive communes, not errors. | no | Keep the values and flag them only for reporting. Check that the top values are plausible for affluent communes before any winsorising. |
| low | avg_price_per_m2_eur | IQR outliers that appear to be genuine high-price communes. | no | Keep the values. Document that the highest per-square-metre prices are concentrated in a few communes. |
| medium | year | Rows per year decline from 116 to 100, so the set of communes changes over time. | yes | Build a list of communes present in every year for trend analysis, or report the commune count alongside year-level averages. Confirm that the drop reflects commune changes and not missing extracts. |
| medium | commune | No spelling-variant check results appear in the facts, though the review scope includes similar-spelling checks. | no | Run a similar-spelling or fuzzy-match check on the 128 names (for example, hyphenation or accent variants such as Esch-sur-Alzette) and merge any variants before joining with other datasets. |
| low | year | The full year range is not confirmed by the profile, but the facts show the expected 2010 to 2025 span. | no | Cast year to integer. Confirm that no years are missing between 2010 and 2025, which the 16 distinct values suggest is complete. |
| low | n_listings | Column is stored as text though it is fully numeric and should be an integer count. | yes | Cast to integer on load and add a check that values are non-negative. |

## Statistics (agent findings)

## Luxembourg apartment asking prices, 2010–2025: findings

**How prices changed nationally** (`trend`). These figures use only rows with a published price. The 620 suppressed ('*') rows count as missing, and so do rows with zero listings.
- **Median asking price per commune:** €328,999 in 2010, peaking at €829,814 in 2022. It then fell to €721,903 in 2023 and €705,323 in 2024, and was €713,460 in 2025. The mean follows the same path: €336,238 → €845,198 (2022) → €750,777 (2025).
- **Median price per m²:** €3,619 in 2010, peaking at €8,470 in 2022. It dropped to €7,427 in 2024 and recovered slightly to €7,661 in 2025. The mean rose from €3,636 to €8,810 (2022), then was €7,991 in 2025.
- **When it rose fastest:** The biggest jumps came in 2019–2021. The median price per m² went from €5,176 (2018) to €6,063 (2019), €7,074 (2020) and €7,903 (2021).

**Most and least expensive communes in 2025, by price per m²** (`top_n`; 61 communes had a published value)
- **Most expensive:** Luxembourg €12,362, Bertrange €11,331, Strassen €10,780, Niederanven €10,327, Hesperange €10,040.
- **Least expensive:** Wiltz €5,628, Esch-sur-Sûre €5,684, Clervaux €5,899, Parc Hosingen €5,917, Goesdorf €6,151. These are all northern, rural communes.

**Fastest growth, 2010 → 2025, price per m²** (`growth`; only the 54 communes with a value in both years)
- **Overall:** The median commune's price rose by 106.4%.
- **Fastest:** Bertrange +163.1% (€4,307 → €11,331), Wormeldange +149.4%, Mersch +148.1%, Steinfort +146.2%, Lintgen +145.9%.
- **Slowest:** Echternach +79.3%, Ettelbruck +81.4%, Esch-sur-Sûre +84.6%, Redange-sur-Attert +86.3%, Mondercange +87.6%. Even the slowest communes saw prices rise by about 80% or more.

**How complete the data is** (`coverage`)
- **Communes listed:** 116 in 2010 and 2011, falling to 100 in 2023–2025. The listing count is filled in for every row.
- **Communes with a published price:** 90 of 116 in 2010, a low of 50 of 102 in 2020, and 61 of 100 in 2025. Altogether 620 of 1,675 rows have a suppressed price.

### Caveats
1. **The set of communes changes from year to year.** The national figures cover between 50 and 94 communes depending on the year, so some of the year-to-year movement may come from which communes are included rather than from real price changes. The growth ranking avoids this by using only the 54 communes with values in both years, but it still leaves out about half the communes.
2. **Suppression probably isn't random.** The 620 suppressed rows are likely communes with few listings, which tend to be small and rural. If so, the national figures lean towards larger markets and may overstate typical prices. I reported medians next to means because the high-price outliers were deliberately kept in.
3. **These are asking prices, not sale prices.** Each figure is an average per commune with no weighting by number of listings, so it shows the typical commune, not the typical apartment. Also, the planned check for commune names with similar spellings wasn't run with these tools. It must be done before joining this data to any other source.

## Cost

| Step | Model | Calls | Input tokens | Output tokens |
|---|---|---|---|---|
| profile | claude-haiku-5-5 | 1 | 2286 | 2508 |
| quality | claude-haiku-5-5 | 1 | 3535 | 3371 |
| integrity | claude-haiku-5-5 | 1 | 4395 | 1535 |
| statistics | claude-opus-5-5 | 2 | 8283 | 1882 |
| summary | claude-opus-5-5 | 1 | 8285 | 2109 |
